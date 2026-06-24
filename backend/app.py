"""TamonRadar(多聞情報雷達) — FastAPI 後端。

把原本的 CLI 爬蟲包成 Web API:前端送關鍵字 → 背景爬 → SSE 即時回報 →
回傳結構化結果 → 提供篩選用資料、匯出、AI 摘要、歷史紀錄。
"""
import asyncio
import io
import json
import os

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from crawler.config import CrawlConfig, DEFAULT_KEYWORDS
from crawler.reporter import to_dataframe, save_excel, save_markdown_report
import db
import auth
import ai
import mailer
import notify
import scheduler
import uploader
import bots
import insights as insights_mod
from oauth_google import router as google_router
from oauth_google import _frontend as _frontend_url
from jobs import manager

app = FastAPI(title="TamonRadar API", version="2.0")
app.include_router(google_router)


@app.on_event("startup")
def _startup():
    # 即使 DB 連不上也別讓服務崩潰重啟(才看得到 log、health 仍可回應)
    try:
        db.init_db()
    except Exception as e:
        print(f"[startup] ⚠️ 資料庫初始化失敗,請檢查 DATABASE_URL:{e}")
    try:
        scheduler.start()
    except Exception as e:
        print(f"[startup] ⚠️ 排程啟動失敗:{e}")

# 允許跨來源的前端網址,可用環境變數 CORS_ORIGINS(逗號分隔)覆寫。
# 去掉結尾斜線:瀏覽器送的 Origin 不含斜線,帶斜線會比對失敗。
_cors = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_allow_origins = [o.strip().rstrip("/") for o in _cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- request / response models ----------

class CrawlRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    google_pages_per_keyword: int = 2
    max_detail_pages: int = 20
    headless: bool = True
    scrape_details: bool = True
    search_provider: str | None = None   # brave | serpapi | selenium;None=自動
    vertical: str = ""                   # 搜尋領域:merch/food/pet/...(影響分類框架)


class SummarizeRequest(BaseModel):
    run_id: str | None = None
    records: list[dict] | None = None
    query: str | None = None


class ChatRequest(BaseModel):
    run_id: str
    question: str
    history: list[dict] | None = None


class CompareRequest(BaseModel):
    run_id: str
    urls: list[str]


class AssistantRequest(BaseModel):
    question: str
    history: list[dict] | None = None


class KeywordsRequest(BaseModel):
    query: str


class AuthRequest(BaseModel):
    email: str
    password: str


class ForgotRequest(BaseModel):
    email: str


class ResetRequest(BaseModel):
    token: str
    password: str


class SettingsRequest(BaseModel):
    discord_webhook: str = ""
    discord_user_id: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    openai_key: str = ""
    anthropic_key: str = ""
    gemini_key: str = ""
    groq_key: str = ""
    openrouter_key: str = ""
    ai_provider: str = ""
    daily_digest: bool = False


class ScheduleRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    provider: str = "brave"
    pages: int = 2
    max_detail: int = 0
    scrape_details: bool = False
    interval_hours: int = 24
    enabled: bool = True


class WatchRequest(BaseModel):
    name: str = ""
    url: str
    available_keywords: list[str] = Field(default_factory=list)
    unavailable_keywords: list[str] = Field(default_factory=list)
    interval_minutes: int = 5
    enabled: bool = True
    target_price: int | None = None
    mode: str = "stock"
    notify_on: list[str] = Field(default_factory=lambda: ["new", "removed", "price", "restock"])


# ---------- helpers ----------

def _ip(request: Request) -> str:
    """取用戶端 IP(優先 Cloudflare/反代標頭)。"""
    return (request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "")) or ""


# ---------- auth ----------

def _public_user(user) -> dict:
    priv = bool(getattr(user, "privileged", False))
    return {
        "id": user.id,
        "email": user.email,
        "username": getattr(user, "username", "") or user.email.split("@")[0],
        "plan": "max" if priv else getattr(user, "plan", "free"),
        "privileged": priv,
        "email_verified": bool(getattr(user, "email_verified", False)) or getattr(user, "provider", "local") != "local",
        "is_admin": auth.is_admin(user.email),
        "is_owner": auth.is_owner(user.email),
    }


def _send_verify_email(user) -> None:
    import mailer
    if not mailer.mail_available() or getattr(user, "provider", "local") != "local":
        return
    try:
        from oauth_google import _frontend as _fe
        token = auth.create_verify_token(user.id)
        link = f"{_fe()}/auth/verify?token={token}"
        html = (f"<p>哈囉 {user.username or user.email},</p>"
                f"<p>感謝註冊 TamonRadar!請點下面連結驗證你的 Email:</p>"
                f'<p><a href="{link}">驗證我的 Email</a></p>'
                f"<p>若不是你本人操作,請忽略這封信。</p>")
        mailer.send_email(user.email, "驗證你的 TamonRadar 帳號", html)
    except Exception:
        pass


@app.post("/api/auth/register")
def register(req: AuthRequest):
    email = req.email.strip().lower()
    if "@" not in email or len(email) < 5:
        raise HTTPException(400, "請輸入有效的 email")
    if len(req.password) < 6:
        raise HTTPException(400, "密碼至少 6 個字")
    with db.SessionLocal() as s:
        exists = s.scalar(select(db.User).where(db.User.email == email))
        if exists:
            raise HTTPException(409, "這個 email 已經註冊過了")
        user = db.User(email=email, password_hash=auth.hash_password(req.password), username=email.split("@")[0])
        s.add(user)
        s.commit()
        s.refresh(user)
        _send_verify_email(user)
        return {"token": auth.create_token(user.id), "user": _public_user(user)}


class VerifyEmailRequest(BaseModel):
    token: str


@app.post("/api/auth/verify-email")
def verify_email(req: VerifyEmailRequest):
    uid = auth.verify_email_token(req.token)
    if uid is None:
        raise HTTPException(400, "驗證連結無效或已過期")
    db.mark_email_verified(uid)
    return {"ok": True}


@app.post("/api/auth/resend-verify")
def resend_verify(user=Depends(auth.get_current_user)):
    import mailer
    if not mailer.mail_available():
        raise HTTPException(400, "後端尚未設定寄信")
    _send_verify_email(user)
    return {"ok": True}


@app.post("/api/auth/login")
def login(req: AuthRequest):
    email = req.email.strip().lower()
    with db.SessionLocal() as s:
        user = s.scalar(select(db.User).where(db.User.email == email))
        if user is None or not auth.verify_password(req.password, user.password_hash):
            raise HTTPException(401, "email 或密碼錯誤")
        return {"token": auth.create_token(user.id), "user": _public_user(user)}


@app.get("/api/auth/me")
def me(user=Depends(auth.get_current_user)):
    return {"user": _public_user(user)}


class ChangePwRequest(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/change-password")
def change_password(req: ChangePwRequest, user=Depends(auth.get_current_user)):
    if user.provider != "local":
        raise HTTPException(400, "第三方登入的帳號沒有密碼可改")
    if not auth.verify_password(req.current_password, user.password_hash):
        raise HTTPException(401, "目前密碼錯誤")
    if len(req.new_password) < 6:
        raise HTTPException(400, "新密碼至少 6 個字")
    db.change_password(user.id, auth.hash_password(req.new_password))
    return {"ok": True}


@app.delete("/api/auth/me")
def delete_account(user=Depends(auth.get_current_user)):
    db.delete_user(user.id)
    return {"ok": True}


@app.post("/api/auth/forgot")
def forgot_password(req: ForgotRequest):
    email = req.email.strip().lower()
    with db.SessionLocal() as s:
        user = s.scalar(select(db.User).where(db.User.email == email))
    # 不論帳號是否存在都回相同訊息,避免洩漏哪些 email 有註冊
    if user and user.provider == "local" and mailer.mail_available():
        token = auth.create_reset_token(user.id)
        link = f"{_frontend_url()}/reset#token={token}"
        html = (
            "<div style='font-family:sans-serif'>"
            "<h2>📡 TamonRadar 密碼重設</h2>"
            "<p>點下面的連結重設密碼(1 小時內有效):</p>"
            f"<p><a href='{link}'>{link}</a></p>"
            "<p>如果不是你本人申請,忽略這封信即可。</p></div>"
        )
        mailer.send_email(email, "TamonRadar 密碼重設", html)
    return {"ok": True, "message": "若這個 email 有註冊,我們已寄出重設連結,請查收信箱。"}


@app.post("/api/auth/reset")
def reset_password(req: ResetRequest):
    user_id = auth.verify_reset_token(req.token)
    if not user_id:
        raise HTTPException(400, "重設連結已失效或不正確,請重新申請")
    if len(req.password) < 6:
        raise HTTPException(400, "密碼至少 6 個字")
    with db.SessionLocal() as s:
        user = s.get(db.User, user_id)
        if not user:
            raise HTTPException(404, "使用者不存在")
        user.password_hash = auth.hash_password(req.password)
        s.commit()
    return {"ok": True}


# ---------- crawl ----------

@app.get("/")
def root():
    return {
        "service": "TamonRadar API",
        "status": "ok",
        "hint": "這是後端 API,請從前端網站使用。健康檢查:/api/health,文件:/docs",
    }


MAX_UPLOAD = 50 * 1024 * 1024  # 50MB


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(auth.get_current_user)):
    """上傳任意檔案到 R2,回傳公開網址(圖片/影片/音樂/檔案皆可)。"""
    if not uploader.r2_available():
        raise HTTPException(503, "後端尚未設定 R2 儲存(R2_* 環境變數)")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "檔案太大(上限 50MB)")
    try:
        url = uploader.upload(file.filename or "file", data, file.content_type or "")
    except Exception as e:
        raise HTTPException(500, f"上傳失敗:{e}")
    return {"url": url, "name": file.filename, "type": file.content_type}


@app.post("/api/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != os.environ.get("TELEGRAM_WEBHOOK_SECRET", "tamon"):
        raise HTTPException(403, "invalid secret")
    update = await request.json()
    bots.handle_telegram_async(update)
    return {"ok": True}


@app.post("/api/admin/telegram/setup")
def telegram_setup(request: Request, admin=Depends(auth.get_admin)):
    base = os.environ.get("OAUTH_REDIRECT_BASE") or str(request.base_url).rstrip("/")
    return bots.telegram_set_webhook(base)


@app.post("/api/discord/interactions")
async def discord_interactions(request: Request):
    sig = request.headers.get("X-Signature-Ed25519")
    ts = request.headers.get("X-Signature-Timestamp")
    body = await request.body()
    if not bots.verify_discord(sig, ts, body):
        raise HTTPException(401, "bad request signature")
    data = json.loads(body)
    if data.get("type") == 1:
        return {"type": 1}  # PING
    if data.get("type") == 2:  # 斜線指令
        cmd = data.get("data", {}).get("name", "")
        opts = data.get("data", {}).get("options", [])
        u = (data.get("member") or {}).get("user") or data.get("user") or {}
        uname = u.get("username") or u.get("global_name") or str(u.get("id", ""))
        if cmd == "bind":  # /bind 綁定碼 → 立即(ephemeral)回覆
            code = next((o.get("value", "") for o in opts if o.get("name") == "code"), "")
            msg = bots.discord_bind(code, str(u.get("id", "")))
            return {"type": 4, "data": {"content": msg, "flags": 64}}
        q = next((o.get("value", "") for o in opts if o.get("name") == "question"), "")
        bots.handle_discord_command_async(data.get("application_id"), data.get("token"), q, uname)
        return {"type": 5}  # 先 defer,背景算完再 followup 編輯回覆
    return {"type": 4, "data": {"content": "?"}}


@app.post("/api/admin/discord/setup")
def discord_setup(admin=Depends(auth.get_admin)):
    return bots.discord_register_command()


@app.post("/api/assistant")
def assistant(req: AssistantRequest, user=Depends(auth.get_optional_user)):
    """前台 AI 助手:回答網站問題;若已登入,還會帶入使用者最近的搜尋結果以便比價/找代購。"""
    from knowledge import KNOWLEDGE
    import money

    args = _ai_args(user) if user else {}
    if not ai.ai_available(**args):
        return {"available": False, "answer": "AI 助手暫時無法使用(尚未設定 AI 金鑰)。"}

    # 帶入該使用者最近一次的搜尋結果,讓小幫手能回答「哪個最便宜 / 哪裡有代購」
    context = ""
    if user:
        try:
            runs = db.list_runs(user.id)
            if runs:
                run = db.get_run(runs[0]["id"], user.id) or {}
                slim = [{
                    "title": r.get("title", ""), "url": r.get("url", ""), "domain": r.get("domain", ""),
                    "price": r.get("price", ""), "price_twd": money.to_twd(r.get("price", "")),
                    "category": r.get("category", ""), "is_listing": r.get("is_listing", False),
                } for r in run.get("records", [])[:60]]
                if slim:
                    kw = "、".join(run.get("keywords", []))
                    context = (
                        f"\n\n【使用者最近一次搜尋「{kw}」的結果】(JSON;price_twd 是換算後台幣可用來比價;"
                        f"is_listing=true 代表是搜尋/列表頁、不是單一商品):\n{json.dumps(slim, ensure_ascii=False)}"
                    )
        except Exception:
            context = ""

    hist = ""
    for h in (req.history or [])[-6:]:
        who = "使用者" if h.get("role") == "user" else "助手"
        hist += f"{who}:{h.get('content', '')}\n"

    prompt = (
        KNOWLEDGE + context
        + "\n\n你是 TamonRadar 的助手,用繁體中文、友善簡潔回答。"
        "若使用者問到比價/哪個最便宜/哪裡買/哪裡有代購,優先依據上面的搜尋結果回答"
        "(用 price_twd 比較、附上連結);資料裡沒有就老實說,或建議去搜尋。\n\n"
        + (f"先前對話:\n{hist}\n" if hist else "")
        + f"使用者問題:{req.question}"
    )
    answer, _ = ai.ai_complete(prompt, max_tokens=900, user_id=(user.id if user else None), **args)
    if user:
        db.add_ai_chat_log(user.id, "assistant", req.question, answer or "")
    return {"available": True, "answer": answer}


@app.get("/api/go/{target}")
def go_redirect(target: str):
    """轉址到社群連結(真實邀請藏在後端,只在登入後的設定頁露出此短連結)。"""
    urls = {
        "discord": os.environ.get("DISCORD_INVITE_URL", "https://discord.gg/yMVZNZE8W"),
        "telegram": os.environ.get("TELEGRAM_BOT_URL", "https://t.me/TamonRadarsBot"),
    }
    url = urls.get(target)
    if not url:
        raise HTTPException(404, "未知的連結")
    return RedirectResponse(url, status_code=302)


class InsightsRequest(BaseModel):
    run_id: str | None = None
    records: list[dict] | None = None
    vertical: str = ""


@app.post("/api/insights")
def insights_endpoint(req: InsightsRequest):
    records = req.records
    if records is None and req.run_id:
        run = db.get_run(req.run_id)
        records = (run or {}).get("records", []) if run else []
    return insights_mod.deep_insights(records or [], req.vertical)


@app.get("/api/insights/compare/{run_id}")
def insights_compare(run_id: str):
    return db.compare_runs(run_id)


@app.post("/api/insights/ai")
def insights_ai(req: InsightsRequest, user=Depends(auth.get_optional_user)):
    records = req.records
    if records is None and req.run_id:
        run = db.get_run(req.run_id)
        records = (run or {}).get("records", []) if run else []
    ins = insights_mod.deep_insights(records or [], req.vertical)
    st = ins.get("price_stats") or {}
    deals = "、".join(f"{d['title']}(NT${d['price_twd']})" for d in ins.get("good_deals", [])[:5])
    clusters = "、".join(f"{c['title']}×{c['count']}站最低NT${c.get('min_twd')}" for c in ins.get("clusters", [])[:5])
    prompt = (
        "你是購物/情報分析顧問,根據以下抓取分析,用繁體中文給出結構化洞察。"
        "用 Markdown,分三段:## 💡 購買建議(最值得買哪個、為何)、## ⚠️ 風險提醒(假貨/價格異常/缺貨等)、## 📊 行情解讀(整體價位與趨勢)。精簡具體。\n\n"
        f"領域:{req.vertical}\n行情:{st}\n好價:{deals}\n跨站聚合:{clusters}\n"
        f"狀態分佈:{ins.get('status_dist')}\n來源分佈:{ins.get('trust_dist')}\n異常:{[o.get('title') for o in ins.get('outliers', [])]}"
    )
    keys = db.get_settings(user.id) if user else {}
    text, model = ai.ai_complete(prompt, max_tokens=900, user_keys=keys, user_id=(user.id if user else None))
    if not text:
        raise HTTPException(400, "AI 暫時無法使用,請於後台設定 AI 金鑰")
    # 可點實體:把洞察提到的關鍵商品附上連結
    entities, seen = [], set()
    def _add(it, note):
        if it and it.get("url") and it["url"] not in seen:
            seen.add(it["url"])
            entities.append({"title": it.get("title", ""), "url": it["url"],
                             "price_twd": it.get("price_twd"), "domain": it.get("domain", ""), "note": note})
    _add(ins.get("best_value"), "最佳CP值")
    _add(ins.get("cheapest"), "最低價")
    for d in ins.get("good_deals", [])[:3]:
        _add(d, f"好價 ↓{d.get('discount_pct', '')}%")
    return {"insight": text, "model": model, "entities": entities}


@app.get("/api/health")
def health():
    from crawler.search_api import available_providers
    from crawler.config import _default_provider
    return {
        "ok": True,
        "default_keywords": DEFAULT_KEYWORDS,
        "search_providers": available_providers(),
        "default_provider": _default_provider(),
    }


class ScrapePageRequest(BaseModel):
    url: str


@app.post("/api/scrape-page")
def scrape_page(req: ScrapePageRequest, user=Depends(auth.get_current_user)):
    """整頁抓取:給一個網址,抓出該頁所有表格列/商品(股票排行、列表頁適用)。"""
    _enforce_quota(user, "search")
    if not req.url.strip().startswith("http"):
        raise HTTPException(400, "請貼有效的網址(http/https)")
    import uuid
    from crawler.detail_scraper import scrape_full_page
    from crawler.reporter import to_dataframe, build_summary
    try:
        recs = scrape_full_page(req.url.strip())
    except Exception as e:
        raise HTTPException(400, f"抓取失敗:{e}")
    df = to_dataframe(recs)
    summary = build_summary(df)
    records = df.to_dict(orient="records")
    rid = uuid.uuid4().hex[:12]
    db.create_run_record(user.id, rid, [req.url.strip()], {"records": records, "summary": summary})
    return {"run_id": rid, "records": records, "summary": summary}


class SiteCrawlRequest(BaseModel):
    url: str
    max_pages: int = 30
    max_depth: int = 2


@app.post("/api/crawl-site")
def start_site_crawl(req: SiteCrawlRequest, user=Depends(auth.get_current_user)):
    """整站爬(背景任務):跟著同網域連結遞迴抓取,進度走同一套 SSE。"""
    _enforce_quota(user, "search")
    if not req.url.strip().startswith("http"):
        raise HTTPException(400, "請貼有效的網址(http/https)")
    config = CrawlConfig(
        keywords=[req.url.strip()],
        site_url=req.url.strip(),
        site_max_pages=req.max_pages,
        site_max_depth=req.max_depth,
    )
    job = manager.create(config, user.id)
    return {"job_id": job.id, "status": job.status}


@app.post("/api/crawl")
def start_crawl(req: CrawlRequest, user=Depends(auth.get_current_user)):
    _enforce_quota(user, "search")
    config = CrawlConfig(
        keywords=req.keywords,
        google_pages_per_keyword=req.google_pages_per_keyword,
        max_detail_pages=req.max_detail_pages,
        headless=req.headless,
        scrape_details=req.scrape_details,
        search_provider=req.search_provider or CrawlConfig().search_provider,
        vertical=req.vertical,
    )
    job = manager.create(config, user.id)
    return {"job_id": job.id, "status": job.status}


@app.get("/api/crawl/{job_id}")
def get_crawl(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "找不到這個任務")
    return {
        "job_id": job.id,
        "status": job.status,
        "error": job.error,
        "result": job.result,
        "events": job.events,
    }


@app.post("/api/crawl/{job_id}/stop")
def stop_crawl(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "找不到這個任務")
    job.request_stop()
    return {"job_id": job.id, "status": "stopping"}


@app.get("/api/crawl/{job_id}/stream")
async def stream_crawl(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "找不到這個任務")

    async def event_generator():
        sent = 0
        while True:
            new_events = job.events_since(sent)
            for event in new_events:
                sent += 1
                yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}
            if job.finished and sent >= len(job.events):
                yield {
                    "event": "end",
                    "data": json.dumps(
                        {"status": job.status, "result": job.result, "error": job.error},
                        ensure_ascii=False,
                    ),
                }
                break
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


# ---------- history ----------

@app.get("/api/history")
def get_history(user=Depends(auth.get_current_user)):
    return {"runs": db.list_runs(user.id)}


@app.get("/api/history/{run_id}")
def get_history_run(run_id: str, user=Depends(auth.get_current_user)):
    run = db.get_run(run_id, user.id)
    if not run:
        raise HTTPException(404, "找不到這筆歷史紀錄")
    return run


class ShareRequest(BaseModel):
    shared: bool


@app.post("/api/history/{run_id}/share")
def history_share(run_id: str, req: ShareRequest, user=Depends(auth.get_current_user)):
    if not db.set_run_shared(run_id, user.id, req.shared):
        raise HTTPException(404, "找不到這筆歷史紀錄")
    return {"shared": req.shared}


@app.get("/api/share/{run_id}")
def public_share(run_id: str):
    run = db.get_shared_run(run_id)
    if not run:
        raise HTTPException(404, "這個分享連結不存在或已關閉")
    return run


@app.get("/api/history/{run_id}/diff")
def history_diff(run_id: str, user=Depends(auth.get_current_user)):
    import radar
    run = db.get_run(run_id, user.id)
    if not run:
        raise HTTPException(404, "找不到這筆歷史紀錄")
    prev = db.previous_run(user.id, run.get("finished_at") or "", run_id)
    if not prev:
        return {"has_previous": False}
    return {
        "has_previous": True,
        "previous_id": prev["id"],
        "previous_at": prev["finished_at"],
        "diff": radar.compute_diff(run.get("records", []), prev.get("records", [])),
    }


# ---------- export ----------
# 注意:匯出是瀏覽器直接點連結下載,沒法帶 Authorization header,
# 所以這裡靠「不可猜的 run_id」當作存取權杖(與 SSE 串流同一個取捨)。

def _records_for(run_id: str) -> list[dict]:
    """匯出時的資料來源:先找進行中的 job,再找資料庫歷史。"""
    job = manager.get(run_id)
    if job and job.result:
        return job.result.get("records", [])
    run = db.get_run(run_id)
    if run:
        return run.get("records", [])
    raise HTTPException(404, "找不到可匯出的資料")


@app.get("/api/export/{run_id}.csv")
def export_csv(run_id: str):
    df = to_dataframe(_records_for(run_id))
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    data = "﻿" + buf.getvalue()  # BOM 讓 Excel 正確顯示中文
    return Response(
        content=data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="tammon_{run_id}.csv"'},
    )


@app.get("/api/export/{run_id}.xlsx")
def export_xlsx(run_id: str):
    import tempfile
    from pathlib import Path

    df = to_dataframe(_records_for(run_id))
    tmp = Path(tempfile.gettempdir())
    path = save_excel(df, str(tmp), name=f"tammon_{run_id}.xlsx")
    data = path.read_bytes()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="tammon_{run_id}.xlsx"'},
    )


@app.get("/api/export/{run_id}.md")
def export_md(run_id: str):
    import tempfile
    from pathlib import Path

    df = to_dataframe(_records_for(run_id))
    tmp = Path(tempfile.gettempdir())
    path = save_markdown_report(df, str(tmp), name=f"tammon_{run_id}.md")
    data = path.read_text(encoding="utf-8")
    return Response(
        content=data.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="tammon_{run_id}.md"'},
    )


# ---------- AI ----------

def _user_records(run_id: str, user) -> list[dict]:
    """取得屬於該使用者的某次結果(進行中的 job 或資料庫歷史)。"""
    job = manager.get(run_id)
    if job and job.result and getattr(job, "user_id", None) == user.id:
        return job.result.get("records", [])
    run = db.get_run(run_id, user.id)
    if run:
        return run.get("records", [])
    raise HTTPException(404, "找不到資料")


def _slim_records(records: list[dict], limit: int = 80) -> list[dict]:
    keys = ("title", "url", "domain", "category", "character", "price", "snippet")
    return [{k: r.get(k, "") for k in keys} for r in records[:limit]]


def _ai_args(user) -> dict:
    """讀使用者自備的 AI 金鑰(沒填則 ai 模組會自動退回後端共用金鑰)。"""
    st = db.get_settings(user.id)
    return {
        "user_keys": {k: st.get(k, "") for k in
                      ("openai_key", "anthropic_key", "gemini_key", "groq_key", "openrouter_key")},
        "prefer": st.get("ai_provider", ""),
    }


def _enforce_quota(user, kind: str) -> None:
    """免費使用者的每日額度;特權或付費方案不受限。"""
    if user is None or getattr(user, "privileged", False) or getattr(user, "plan", "free") != "free":
        return
    if auth.is_admin(user.email):
        return
    limit = int(os.environ.get("FREE_AI_DAILY", "30") if kind == "ai" else os.environ.get("FREE_SEARCH_DAILY", "15"))
    ok, _used = db.quota_use(user.id, kind, limit)
    if not ok:
        raise HTTPException(429, f"今日免費{'AI' if kind == 'ai' else '搜尋'}額度已用完(每日 {limit} 次)。升級方案或明天再來。")


@app.get("/api/push/key")
def push_key():
    import push
    return {"key": push.public_key()}


class PushSubRequest(BaseModel):
    endpoint: str
    keys: dict


@app.post("/api/push/subscribe")
def push_subscribe(req: PushSubRequest, user=Depends(auth.get_current_user)):
    db.add_push_sub(user.id, req.endpoint, req.keys.get("p256dh", ""), req.keys.get("auth", ""))
    return {"ok": True}


class PushUnsubRequest(BaseModel):
    endpoint: str


@app.post("/api/push/unsubscribe")
def push_unsubscribe(req: PushUnsubRequest, user=Depends(auth.get_current_user)):
    db.remove_push_sub(req.endpoint)
    return {"ok": True}


@app.get("/api/notifications")
def get_notifications(user=Depends(auth.get_current_user)):
    return db.list_notifications(user.id)


@app.post("/api/notifications/read")
def read_notifications(user=Depends(auth.get_current_user)):
    db.mark_notifications_read(user.id)
    return {"ok": True}


@app.get("/api/quota")
def get_quota(user=Depends(auth.get_current_user)):
    unlimited = bool(getattr(user, "privileged", False)) or getattr(user, "plan", "free") != "free" or auth.is_admin(user.email)
    used = db.quota_today(user.id)
    return {
        "unlimited": unlimited,
        "ai_used": used["ai"], "search_used": used["search"],
        "ai_limit": int(os.environ.get("FREE_AI_DAILY", "30")),
        "search_limit": int(os.environ.get("FREE_SEARCH_DAILY", "15")),
    }


@app.post("/api/ai/chat")
def ai_chat(req: ChatRequest, user=Depends(auth.get_current_user)):
    _enforce_quota(user, "ai")
    records = _user_records(req.run_id, user)
    args = _ai_args(user)
    if not ai.ai_available(**args):
        return {"available": False, "answer": "尚未設定 AI 金鑰(可在「設定」填自己的,或由後端提供)。"}
    hist = ""
    for h in (req.history or [])[-6:]:
        who = "使用者" if h.get("role") == "user" else "助手"
        hist += f"{who}:{h.get('content', '')}\n"
    prompt = (
        "你是一個資料查詢助理。以下是一批網路搜尋結果(JSON)。請根據這些資料用繁體中文回答"
        "使用者的問題;提到具體項目時附上連結(若有價格、日期、數據也一併附上),"
        "資料裡沒有就老實說。\n\n"
        + (f"先前對話:\n{hist}\n" if hist else "")
        + f"使用者問題:{req.question}\n\n資料:\n{json.dumps(_slim_records(records), ensure_ascii=False)}"
    )
    answer, model = ai.ai_complete(prompt, max_tokens=1500, user_id=user.id, **args)
    db.add_ai_chat_log(user.id, "chat", req.question, answer or "")
    db.bump_ai_usage(user.id)
    return {"available": True, "answer": answer, "model": model}


@app.post("/api/ai/compare")
def ai_compare(req: CompareRequest, user=Depends(auth.get_current_user)):
    _enforce_quota(user, "ai")
    records = _user_records(req.run_id, user)
    args = _ai_args(user)
    if not ai.ai_available(**args):
        return {"available": False, "answer": "尚未設定 AI 金鑰。"}
    chosen = [r for r in records if r.get("url") in set(req.urls)][:8]
    if len(chosen) < 2:
        raise HTTPException(400, "請至少選 2 個商品比較")
    import money
    slim = [{
        "title": r.get("title", ""), "url": r.get("url", ""), "price": r.get("price", ""),
        "price_twd": money.to_twd(r.get("price", "")), "category": r.get("category", ""),
        "snippet": r.get("snippet", ""),
    } for r in chosen]
    prompt = (
        "比較以下幾個商品(JSON),用繁體中文 Markdown 表格列出:名稱、價格(台幣)、重點差異/規格、"
        "並在最後給「最划算」與「最推薦」各一個建議(附連結)。\n\n"
        f"商品:\n{json.dumps(slim, ensure_ascii=False)}"
    )
    answer, _ = ai.ai_complete(prompt, max_tokens=1500, user_id=user.id, **args)
    db.bump_ai_usage(user.id)
    return {"available": True, "answer": answer}


@app.post("/api/ai/keywords")
def ai_keywords(req: KeywordsRequest, user=Depends(auth.get_current_user)):
    args = _ai_args(user)
    if not ai.ai_available(**args):
        return {"available": False, "keywords": []}
    _enforce_quota(user, "ai")
    prompt = (
        "把以下需求展開成 5-8 個適合在購物/搜尋引擎使用的繁體中文關鍵字。"
        "只回 JSON 字串陣列,不要其他文字。\n需求:" + req.query
    )
    text, _ = ai.ai_complete(prompt, max_tokens=300, user_id=user.id, **args)
    kws: list[str] = []
    try:
        s, e = (text or "").find("["), (text or "").rfind("]")
        if s >= 0 and e > s:
            kws = [str(x).strip() for x in json.loads(text[s:e + 1]) if str(x).strip()][:8]
    except Exception:
        kws = []
    db.bump_ai_usage(user.id)
    return {"available": True, "keywords": kws}


@app.post("/api/ai/clean")
def ai_clean(req: SummarizeRequest, user=Depends(auth.get_current_user)):
    if not req.run_id:
        raise HTTPException(400, "請提供 run_id")
    records = _user_records(req.run_id, user)
    args = _ai_args(user)
    if not ai.ai_available(**args):
        return {"available": False, "noise_urls": [], "message": "尚未設定 AI 金鑰"}
    _enforce_quota(user, "ai")
    prompt = (
        "以下是一批網路搜尋結果 JSON。請判斷哪些是『沒有實質內容的雜訊』"
        "(例如純搜尋結果頁、空白/錯誤頁、與搜尋主題明顯無關的內容)。\n"
        "只回傳 JSON,格式:{\"noise_urls\": [\"...\"]},不要其他文字。\n\n"
        f"資料:\n{json.dumps(_slim_records(records, 100), ensure_ascii=False)}"
    )
    text, _ = ai.ai_complete(prompt, max_tokens=1500, user_id=user.id, **args)
    db.bump_ai_usage(user.id)
    noise: list[str] = []
    try:
        start, end = (text or "").find("{"), (text or "").rfind("}")
        if start >= 0 and end > start:
            noise = json.loads(text[start:end + 1]).get("noise_urls", [])
    except Exception:
        noise = []
    return {"available": True, "noise_urls": noise, "noise_count": len(noise)}


# ---------- AI 摘要 ----------

@app.post("/api/summarize")
def summarize(req: SummarizeRequest, user=Depends(auth.get_current_user)):
    if req.records is not None:
        records = req.records
    elif req.run_id:
        records = _records_for(req.run_id)
    else:
        raise HTTPException(400, "請提供 run_id 或 records")

    args = _ai_args(user)
    if not ai.ai_available(**args):
        return {
            "available": False,
            "summary": "尚未設定 AI 金鑰(可在「設定」填自己的,或由後端提供),無法產生 AI 摘要。",
        }
    _enforce_quota(user, "ai")

    # 自動讀出這次搜尋的主題,讓 AI 針對主題抓重點(支援搜尋任何東西)
    topics = ", ".join(sorted({r.get("keyword", "") for r in records if r.get("keyword")}))[:200] or "(未指定)"
    if req.query:
        topics = req.query

    prompt = (
        "你是一個情報研究助理。使用者搜尋的主題是「" + topics + "」。\n"
        "以下是針對這個主題抓到的一批網路搜尋結果(JSON)。請用繁體中文輸出 Markdown,"
        "從中抓出對這個主題『最重要』的資訊:\n"
        "1. 重點摘要(3-6 點,針對主題)\n"
        "2. 最值得關注的項目/來源(附連結;若資料中有價格、日期、數據、規格等就一併列出)\n"
        "3. 哪些可能是重複、過期或與主題無關的雜訊\n"
        "4. 一句總結建議\n\n"
        "若資料不足以回答,就誠實說明。\n\n"
        f"資料:\n{json.dumps(_slim_records(records, 60), ensure_ascii=False)}"
    )
    text, model = ai.ai_complete(prompt, max_tokens=2000, user_id=user.id, **args)
    db.bump_ai_usage(user.id)
    return {"available": True, "summary": text, "model": model}


# ---------- 通知設定 ----------

@app.get("/api/settings")
def get_settings(user=Depends(auth.get_current_user)):
    return db.get_settings(user.id)


@app.post("/api/bind/code")
def bind_code(user=Depends(auth.get_current_user)):
    return {"code": db.create_bind_code(user.id)}


@app.put("/api/settings")
def put_settings(req: SettingsRequest, user=Depends(auth.get_current_user)):
    db.save_settings(user.id, {
        "discord_webhook": req.discord_webhook.strip(),
        "discord_user_id": req.discord_user_id.strip(),
        "telegram_token": req.telegram_token.strip(),
        "telegram_chat_id": req.telegram_chat_id.strip(),
        "openai_key": req.openai_key.strip(),
        "anthropic_key": req.anthropic_key.strip(),
        "gemini_key": req.gemini_key.strip(),
        "groq_key": req.groq_key.strip(),
        "openrouter_key": req.openrouter_key.strip(),
        "ai_provider": req.ai_provider.strip(),
        "daily_digest": req.daily_digest,
    })
    return {"ok": True}


@app.post("/api/settings/test")
def test_settings(user=Depends(auth.get_current_user)):
    st = db.get_settings(user.id)
    results = notify.notify_all(st, "📡 TamonRadar 測試通知:設定成功!")
    if not results:
        raise HTTPException(400, "尚未設定任何通知管道(Discord 或 Telegram)")
    return {"results": results}


# ---------- 排程 ----------

@app.get("/api/schedules")
def get_schedules(user=Depends(auth.get_current_user)):
    return {"schedules": db.list_schedules(user.id)}


@app.post("/api/schedules")
def create_schedule(req: ScheduleRequest, user=Depends(auth.get_current_user)):
    if not [k for k in req.keywords if k.strip()]:
        raise HTTPException(400, "請至少設定一個關鍵字")
    sc = db.create_schedule(user.id, req.model_dump())
    scheduler.sync(sc)
    return sc


@app.patch("/api/schedules/{schedule_id}")
def patch_schedule(schedule_id: int, req: ScheduleRequest, user=Depends(auth.get_current_user)):
    sc = db.update_schedule(schedule_id, user.id, req.model_dump())
    if not sc:
        raise HTTPException(404, "找不到這個排程")
    scheduler.sync(sc)
    return sc


@app.delete("/api/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user=Depends(auth.get_current_user)):
    if not db.delete_schedule(schedule_id, user.id):
        raise HTTPException(404, "找不到這個排程")
    scheduler.remove(schedule_id)
    return {"ok": True}


@app.post("/api/schedules/{schedule_id}/run")
def run_schedule_now(schedule_id: int, user=Depends(auth.get_current_user)):
    import threading
    sc = db.get_schedule(schedule_id, user.id)
    if not sc:
        raise HTTPException(404, "找不到這個排程")
    threading.Thread(target=scheduler.run_now, args=(schedule_id,), daemon=True).start()
    return {"ok": True, "message": "已在背景開始執行,完成後會依設定推播"}


# ---------- 監看(到貨/開賣通知)----------

@app.get("/api/watches")
def get_watches(user=Depends(auth.get_current_user)):
    return {"watches": db.list_watches(user.id)}


class FavoriteRequest(BaseModel):
    url: str
    title: str = ""
    image_url: str = ""
    domain: str = ""
    price: str = ""


class TargetRequest(BaseModel):
    target_twd: int | None = None


@app.get("/api/favorites")
def get_favorites(user=Depends(auth.get_current_user)):
    return {"favorites": db.list_favorites(user.id), "urls": db.favorite_urls(user.id)}


@app.post("/api/favorites")
def add_favorite(req: FavoriteRequest, user=Depends(auth.get_current_user)):
    if not req.url.strip().startswith("http"):
        raise HTTPException(400, "網址不正確")
    return db.add_favorite(user.id, req.model_dump())


@app.patch("/api/favorites/{fav_id}")
def set_favorite_target(fav_id: int, req: TargetRequest, user=Depends(auth.get_current_user)):
    f = db.set_favorite_target(fav_id, user.id, req.target_twd)
    if not f:
        raise HTTPException(404, "找不到收藏")
    return f


@app.delete("/api/favorites/{fav_id}")
def delete_favorite(fav_id: int, user=Depends(auth.get_current_user)):
    if not db.remove_favorite(fav_id, user.id):
        raise HTTPException(404, "找不到收藏")
    return {"ok": True}


@app.get("/api/price-history")
def get_price_history(url: str, user=Depends(auth.get_current_user)):
    return {"history": db.price_history(user.id, url)}


@app.post("/api/watches")
def create_watch(req: WatchRequest, user=Depends(auth.get_current_user)):
    if not req.url.strip().startswith("http"):
        raise HTTPException(400, "請輸入有效的網址(http/https)")
    w = db.create_watch(user.id, req.model_dump())
    scheduler.sync_watch(w)
    return w


@app.patch("/api/watches/{watch_id}")
def patch_watch(watch_id: int, req: WatchRequest, user=Depends(auth.get_current_user)):
    w = db.update_watch(watch_id, user.id, req.model_dump())
    if not w:
        raise HTTPException(404, "找不到這個監看")
    scheduler.sync_watch(w)
    return w


@app.delete("/api/watches/{watch_id}")
def delete_watch(watch_id: int, user=Depends(auth.get_current_user)):
    if not db.delete_watch(watch_id, user.id):
        raise HTTPException(404, "找不到這個監看")
    scheduler.remove_watch(watch_id)
    return {"ok": True}


@app.post("/api/watches/{watch_id}/check")
def check_watch_now(watch_id: int, user=Depends(auth.get_current_user)):
    import threading
    if not db.get_watch(watch_id, user.id):
        raise HTTPException(404, "找不到這個監看")
    threading.Thread(target=scheduler.check_watch_now, args=(watch_id,), daemon=True).start()
    return {"ok": True, "message": "已在背景檢查一次"}


# ---------- 管理員後台 ----------

class PlanRequest(BaseModel):
    plan: str


@app.get("/api/admin/stats")
def admin_stats(admin=Depends(auth.get_admin)):
    return db.admin_stats()


@app.get("/api/admin/charts")
def admin_charts(admin=Depends(auth.get_admin)):
    return db.admin_charts()


@app.get("/api/admin/crawls")
def admin_crawls(admin=Depends(auth.get_admin)):
    return {"crawls": db.admin_recent_crawls()}


@app.get("/api/admin/ai-costs")
def admin_ai_costs(admin=Depends(auth.get_admin)):
    return db.admin_ai_costs()


@app.get("/api/admin/bot-chats")
def admin_bot_chats(admin=Depends(auth.get_admin)):
    return {"chats": db.list_bot_chats()}


@app.get("/api/admin/env-check")
def admin_env_check(admin=Depends(auth.get_admin)):
    """回報各環境變數有沒有設定(只回布林,不外洩內容)。"""
    def has(k):
        return bool(os.environ.get(k))
    ai_env = any(has(k) for k in ["OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"])
    ai_db = any(db.get_ai_config(masked=True)["providers"][p]["has_key"] for p in db.AI_PROVIDERS)
    search = any(has(k) for k in ["BRAVE_API_KEY", "SERPAPI_KEY", "SERPER_API_KEY", "GOOGLE_CSE_KEY", "TAVILY_API_KEY", "SEARXNG_URL"])
    groups = {
        "核心(必填)": {
            "DATABASE_URL": has("DATABASE_URL"), "JWT_SECRET": has("JWT_SECRET"),
            "CORS_ORIGINS": has("CORS_ORIGINS"), "ADMIN_EMAILS": has("ADMIN_EMAILS"),
        },
        "建議": {
            "ENCRYPTION_KEY": has("ENCRYPTION_KEY"), "OWNER_EMAILS": has("OWNER_EMAILS"),
            "搜尋來源(任一)": search,
        },
        "AI(env 或後台設定任一即可)": {"AI 金鑰(env)": ai_env, "AI 金鑰(後台)": ai_db},
        "通知": {
            "VAPID(Web Push 三個)": has("VAPID_PUBLIC_KEY") and has("VAPID_PRIVATE_KEY") and has("VAPID_SUBJECT"),
            "TELEGRAM_BOT_TOKEN": has("TELEGRAM_BOT_TOKEN"), "TELEGRAM_WEBHOOK_SECRET": has("TELEGRAM_WEBHOOK_SECRET"),
            "DISCORD_BOT_TOKEN": has("DISCORD_BOT_TOKEN"), "DISCORD_PUBLIC_KEY": has("DISCORD_PUBLIC_KEY"),
            "DISCORD_APP_ID": has("DISCORD_APP_ID"), "DISCORD_WEBHOOK(共用,選)": has("DISCORD_WEBHOOK"),
        },
        "檔案/圖片 R2(封面、附圖、AI 封面)": {
            "R2 五項齊全": all(has(k) for k in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_URL"]),
        },
        "Google 登入": {
            "GOOGLE_CLIENT_ID": has("GOOGLE_CLIENT_ID"), "GOOGLE_CLIENT_SECRET": has("GOOGLE_CLIENT_SECRET"),
            "OAUTH_REDIRECT_BASE": has("OAUTH_REDIRECT_BASE"),
        },
        "寄信(驗證/忘記密碼/群發)": {
            "Resend 或 Gmail(任一)": has("RESEND_API_KEY") or (has("GMAIL_USER") and has("GMAIL_APP_PASSWORD")),
        },
    }
    return {"groups": groups}


@app.get("/api/admin/kpi")
def admin_kpi(days: int = 30, admin=Depends(auth.get_admin)):
    return db.kpi_report(days)


@app.get("/api/admin/kpi/export")
def admin_kpi_export(days: int = 30, admin=Depends(auth.get_admin)):
    import csv as _csv
    rep = db.kpi_report(days)
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["日期", "新註冊", "搜尋數", "活躍用戶"])
    for r in rep["daily"]:
        w.writerow([r["date"], r["signups"], r["searches"], r["active"]])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=kpi.csv"})


# ---- 後台:AI 模型 / 金鑰集中設定 ----
@app.get("/api/admin/ai-config")
def admin_ai_config(admin=Depends(auth.get_admin)):
    return db.get_ai_config(masked=True)


class AiConfigRequest(BaseModel):
    provider: str
    key: str | None = None
    model: str | None = None
    enabled: bool | None = None


@app.post("/api/admin/ai-config")
def admin_ai_config_save(req: AiConfigRequest, request: Request, admin=Depends(auth.get_admin)):
    data = {}
    changed = []
    if req.key is not None:
        data["key"] = req.key
        changed.append("key" if req.key.strip() else "key(清除)")
    if req.model is not None:
        data["model"] = req.model
        changed.append(f"model={req.model}")
    if req.enabled is not None:
        data["enabled"] = req.enabled
        changed.append(f"enabled={req.enabled}")
    db.save_ai_config(req.provider, data)
    db.log_audit(admin.email, "ai_config", req.provider, "、".join(changed),
                 target_type="ai_key", changes={"fields": changed}, ip=_ip(request))  # 不記錄金鑰明文
    return {"ok": True}


class AiDefaultRequest(BaseModel):
    provider: str


@app.post("/api/admin/ai-config/default")
def admin_ai_default(req: AiDefaultRequest, admin=Depends(auth.get_admin)):
    db.set_ai_default_provider(req.provider)
    return {"ok": True}


@app.post("/api/admin/ai-config/test")
def admin_ai_test(req: AiConfigRequest, admin=Depends(auth.get_admin)):
    return ai.test_provider(req.provider, req.key or "")


@app.get("/api/admin/users")
def admin_users(admin=Depends(auth.get_admin)):
    return {"users": db.admin_users()}


class NoteRequest(BaseModel):
    admin_note: str = ""
    tags: list[str] = Field(default_factory=list)


@app.get("/api/admin/users/{user_id}")
def admin_user_detail(user_id: int, admin=Depends(auth.get_admin)):
    d = db.get_user_detail(user_id)
    if not d:
        raise HTTPException(404, "找不到使用者")
    return d


@app.get("/api/admin/run/{run_id}")
def admin_run(run_id: str, admin=Depends(auth.get_admin)):
    run = db.get_run(run_id)  # 管理員可看任何人的搜尋結果
    if not run:
        raise HTTPException(404, "找不到這筆紀錄")
    return run


@app.post("/api/admin/users/{user_id}/note")
def admin_user_note(user_id: int, req: NoteRequest, admin=Depends(auth.get_admin)):
    if not db.set_user_note(user_id, req.admin_note, req.tags):
        raise HTTPException(404, "找不到使用者")
    return {"ok": True}


@app.post("/api/admin/users/{user_id}/plan")
def admin_set_plan(user_id: int, req: PlanRequest, admin=Depends(auth.get_admin)):
    if req.plan not in ("free", "pro"):
        raise HTTPException(400, "方案只能是 free 或 pro")
    if not db.set_user_plan(user_id, req.plan):
        raise HTTPException(404, "找不到使用者")
    db.log_audit(admin.email, "set_plan", str(user_id), req.plan)
    return {"ok": True}


class PrivilegeRequest(BaseModel):
    privileged: bool


@app.post("/api/admin/users/{user_id}/privilege")
def admin_set_privilege(user_id: int, req: PrivilegeRequest, request: Request, admin=Depends(auth.get_owner)):
    if not db.set_privilege(user_id, req.privileged):
        raise HTTPException(404, "找不到使用者")
    db.log_audit(admin.email, "privilege" if req.privileged else "unprivilege", str(user_id),
                 target_type="user", changes={"privileged": req.privileged}, ip=_ip(request))
    return {"ok": True}


class BanRequest(BaseModel):
    banned: bool


@app.post("/api/admin/users/{user_id}/ban")
def admin_ban(user_id: int, req: BanRequest, request: Request, admin=Depends(auth.get_owner)):
    if not db.set_banned(user_id, req.banned):
        raise HTTPException(404, "找不到使用者")
    db.log_audit(admin.email, "ban" if req.banned else "unban", str(user_id),
                 target_type="user", changes={"banned": req.banned}, ip=_ip(request))
    return {"ok": True}


@app.get("/api/admin/users/export")
def admin_export_users(admin=Depends(auth.get_admin)):
    import csv
    import io
    rows = db.all_users_for_export()
    buf = io.StringIO()
    fields = ["id", "email", "username", "provider", "plan", "privileged", "banned", "ai_used", "tags", "created_at"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    db.log_audit(admin.email, "export_users", f"{len(rows)} 筆")
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=users.csv"})


@app.get("/api/admin/audit")
def admin_audit(page: int = 1, action: str = "", actor: str = "",
                date_from: str = "", date_to: str = "", admin=Depends(auth.get_admin)):
    per = 50
    page = max(1, page)
    res = db.list_audit(limit=per, offset=(page - 1) * per, action=action, actor=actor,
                        date_from=date_from, date_to=date_to)
    res["page"] = page
    res["per"] = per
    return res


@app.get("/api/admin/audit/export")
def admin_audit_export(action: str = "", actor: str = "", date_from: str = "", date_to: str = "",
                       admin=Depends(auth.get_admin)):
    import csv as _csv
    rows = db.audit_rows_for_export(action=action, actor=actor, date_from=date_from, date_to=date_to)
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["時間", "操作者", "動作", "對象類型", "對象", "IP", "明細"])
    for r in rows:
        w.writerow([r["created_at"], r["admin_email"], r["action"], r["target_type"], r["target"], r["ip"], r["detail"]])
    data = "﻿" + buf.getvalue()  # BOM 讓 Excel 正確顯示中文
    return Response(content=data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=audit.csv"})


@app.get("/api/admin/app-settings")
def admin_app_settings(admin=Depends(auth.get_admin)):
    return {"settings": db.get_app_settings()}


class AppSettingRequest(BaseModel):
    key: str
    value: str = ""


@app.post("/api/admin/app-settings")
def admin_save_app_setting(req: AppSettingRequest, admin=Depends(auth.get_admin)):
    k = req.key.strip()
    if not k:
        raise HTTPException(400, "key 不可為空")
    db.save_app_settings({k: req.value})
    db.log_audit(admin.email, "app_setting", k, req.value[:80])
    return {"ok": True}


# ---- 站內公告 ----
class AnnouncementRequest(BaseModel):
    title: str = ""
    body: str = ""
    level: str = "info"
    active: bool = True


@app.get("/api/announcements")
def public_announcements():
    return {"announcements": db.list_announcements(active_only=True)}


@app.get("/api/admin/announcements")
def admin_announcements(admin=Depends(auth.get_admin)):
    return {"announcements": db.list_announcements()}


@app.post("/api/admin/announcements")
def admin_create_announcement(req: AnnouncementRequest, admin=Depends(auth.get_admin)):
    db.log_audit(admin.email, "announce", req.title)
    return db.create_announcement(req.model_dump())


@app.delete("/api/admin/announcements/{ann_id}")
def admin_delete_announcement(ann_id: int, admin=Depends(auth.get_admin)):
    db.delete_announcement(ann_id)
    return {"ok": True}


# ---- Email 群發 ----
class EmailBlastRequest(BaseModel):
    subject: str
    body: str


@app.post("/api/admin/email-blast")
def admin_email_blast(req: EmailBlastRequest, admin=Depends(auth.get_admin)):
    import mailer
    if not mailer.mail_available():
        raise HTTPException(400, "尚未設定寄信(Resend / Gmail)")
    emails = db.all_user_emails()
    html = req.body.replace("\n", "<br>")
    sent = 0
    for e in emails:
        try:
            ok, _ = mailer.send_email(e, req.subject, html)
            if ok:
                sent += 1
        except Exception:
            pass
    db.log_audit(admin.email, "email_blast", f"{sent}/{len(emails)}", req.subject)
    return {"sent": sent, "total": len(emails)}


# ---- 推播中心(多管道一次發)----
class BroadcastRequest(BaseModel):
    title: str
    body: str = ""
    url: str = ""
    channels: list[str] = Field(default_factory=lambda: ["inapp"])  # inapp / email / tg / discord
    segment: str = "all"   # all / privileged / verified / telegram / discord
    run_at: str | None = None   # ISO 時間;有值=排程,留空=立即


@app.post("/api/admin/broadcast")
def admin_broadcast(req: BroadcastRequest, request: Request, admin=Depends(auth.get_admin)):
    if not req.title.strip():
        raise HTTPException(400, "標題不能空白")
    if req.run_at:
        bid = db.schedule_broadcast(req.title.strip(), req.body, req.url, req.channels, req.segment, req.run_at)
        db.log_audit(admin.email, "broadcast_scheduled", req.title, f"{req.segment}/{req.run_at}",
                     target_type="broadcast", ip=_ip(request))
        return {"ok": True, "scheduled": True, "id": bid}
    result = db.broadcast(req.title.strip(), req.body, req.url, req.channels, req.segment)
    if "email" in req.channels:
        import mailer
        if mailer.mail_available():
            emails = db.all_user_emails()
            html = (f"<h3>{req.title}</h3>" + req.body.replace("\n", "<br>")
                    + (f'<p><a href="{req.url}">前往</a></p>' if req.url else ""))
            sent = 0
            for e in emails:
                try:
                    ok, _ = mailer.send_email(e, req.title, html)
                    sent += 1 if ok else 0
                except Exception:
                    pass
            result["email"] = sent
    db.log_audit(admin.email, "broadcast", req.title, f"{req.segment}・" + "、".join(req.channels),
                 target_type="broadcast", changes={"channels": req.channels, "segment": req.segment}, ip=_ip(request))
    return {"ok": True, **result}


@app.get("/api/admin/broadcasts/scheduled")
def admin_scheduled_broadcasts(admin=Depends(auth.get_admin)):
    return {"items": db.list_scheduled_broadcasts()}


@app.delete("/api/admin/broadcasts/scheduled/{bid}")
def admin_delete_scheduled(bid: int, admin=Depends(auth.get_admin)):
    db.delete_scheduled_broadcast(bid)
    return {"ok": True}


# ---- 檢舉 ----
class ReportRequest(BaseModel):
    target_type: str
    target_id: int
    reason: str = ""


@app.post("/api/report")
def create_report(req: ReportRequest, user=Depends(auth.get_current_user)):
    return db.create_report(user.id, req.target_type, req.target_id, req.reason)


@app.get("/api/admin/reports")
def admin_reports(status: str = "open", admin=Depends(auth.get_admin)):
    return {"reports": db.list_reports(status)}


@app.post("/api/admin/reports/{report_id}/resolve")
def admin_resolve_report(report_id: int, admin=Depends(auth.get_admin)):
    db.resolve_report(report_id)
    db.log_audit(admin.email, "resolve_report", str(report_id))
    return {"ok": True}


# ---- SEO 中繼資料 ----
@app.get("/api/seo")
def public_seo():
    return db.get_app_settings()


@app.post("/api/admin/seo")
def admin_save_seo(req: dict, admin=Depends(auth.get_admin)):
    allowed = {k: str(v) for k, v in req.items() if k in ("site_title", "site_description", "og_image", "keywords")}
    db.save_app_settings(allowed)
    db.log_audit(admin.email, "save_seo", "", ", ".join(allowed.keys()))
    return {"ok": True}


@app.get("/api/seo/page")
def public_page_seo(path: str):
    return db.get_page_seo(path)


@app.get("/api/admin/seo/pages")
def admin_list_page_seo(admin=Depends(auth.get_admin)):
    return {"pages": db.list_page_seo()}


class PageSeoRequest(BaseModel):
    path: str
    title: str = ""
    description: str = ""
    keywords: str = ""


@app.post("/api/admin/seo/page")
def admin_save_page_seo(req: PageSeoRequest, admin=Depends(auth.get_admin)):
    if not req.path.startswith("/"):
        raise HTTPException(400, "路徑要以 / 開頭")
    db.save_page_seo(req.path, req.model_dump())
    db.log_audit(admin.email, "save_page_seo", req.path)
    return {"ok": True}


class ProfileRequest(BaseModel):
    username: str


@app.patch("/api/auth/profile")
def update_profile(req: ProfileRequest, user=Depends(auth.get_current_user)):
    db.set_username(user.id, req.username.strip())
    fresh = db.get_user_detail(user.id)
    return {"ok": True, "username": fresh["username"] if fresh else req.username.strip()}


# ---------- 部落格 ----------

class PostRequest(BaseModel):
    title: str = "未命名"
    slug: str = ""
    excerpt: str = ""
    content: str = ""
    cover_image: str = ""
    category: str = ""
    series: str = ""
    tags: list[str] = Field(default_factory=list)
    published: bool = False
    featured: bool = False
    password: str = ""


@app.get("/api/blog")
def blog_list(category: str | None = None, tag: str | None = None, featured: bool = False):
    return {"posts": db.list_published_posts(category, tag, featured)}


@app.get("/api/blog-taxonomy")
def blog_taxonomy():
    return db.list_blog_taxonomy()


# ---- 使用者自己的部落格(所有登入者都能寫)----
@app.get("/api/blog/mine")
def blog_mine(user=Depends(auth.get_current_user)):
    return {"posts": db.list_user_posts(user.id)}


@app.get("/api/blog/manage/{post_id}")
def blog_manage_get(post_id: int, user=Depends(auth.get_current_user)):
    owner = db.post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "找不到文章")
    if owner != user.id and not auth.is_admin(user.email):
        raise HTTPException(403, "不是你的文章")
    return db.get_post(post_id)


def _notify_subscribers(author, post: dict) -> None:
    """文章發佈時通知作者的訂閱者(email)。"""
    import mailer
    if not mailer.mail_available():
        return
    emails = db.subscriber_emails(author.id)
    if not emails:
        return
    try:
        from oauth_google import _frontend as _fe
        name = getattr(author, "username", "") or author.email.split("@")[0]
        link = f"{_fe()}/blog/{post.get('slug', '')}"
        html = (f"<p>你訂閱的 {name} 發表了新文章:</p>"
                f"<p><a href=\"{link}\">{post.get('title', '')}</a></p>")
        for e in emails[:500]:
            try:
                mailer.send_email(e, f"{name} 發表新文章:{post.get('title', '')}", html)
            except Exception:
                pass
    except Exception:
        pass


@app.post("/api/blog")
def blog_create(req: PostRequest, user=Depends(auth.get_current_user)):
    post = db.create_post(user.id, req.model_dump())
    if req.published:
        _notify_subscribers(user, post)
    return post


@app.put("/api/blog/{post_id}")
def blog_update(post_id: int, req: PostRequest, user=Depends(auth.get_current_user)):
    owner = db.post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "找不到文章")
    if owner != user.id and not auth.is_admin(user.email):
        raise HTTPException(403, "不是你的文章")
    was_published = (db.get_post(post_id) or {}).get("published", False)
    post = db.update_post(post_id, req.model_dump())
    if req.published and not was_published:
        _notify_subscribers(user, post)
    return post


@app.delete("/api/blog/{post_id}")
def blog_delete(post_id: int, user=Depends(auth.get_current_user)):
    owner = db.post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "找不到文章")
    if owner != user.id and not auth.is_admin(user.email):
        raise HTTPException(403, "不是你的文章")
    db.delete_post(post_id)
    return {"ok": True}


@app.get("/api/blog/author/{author_id}")
def blog_author(author_id: int):
    d = db.get_author_blog(author_id)
    if not d:
        raise HTTPException(404, "找不到這個作者")
    return d


@app.post("/api/blog/author/{author_id}/subscribe")
def blog_subscribe(author_id: int, user=Depends(auth.get_current_user)):
    db.subscribe(user.id, author_id)
    return {"subscribed": True}


@app.delete("/api/blog/author/{author_id}/subscribe")
def blog_unsubscribe(author_id: int, user=Depends(auth.get_current_user)):
    db.unsubscribe(user.id, author_id)
    return {"subscribed": False}


@app.get("/api/blog/author/{author_id}/subscribed")
def blog_subscribed(author_id: int, user=Depends(auth.get_current_user)):
    return {"subscribed": db.is_subscribed(user.id, author_id)}


@app.get("/api/blog/{slug}")
def blog_get(slug: str, user=Depends(auth.get_optional_user)):
    p = db.get_post_by_slug(slug)
    if not p:
        raise HTTPException(404, "找不到文章")
    # 密碼文章:未解鎖前不送內文(作者/管理員例外)
    if p.get("has_password") and not (user and (user.id == p.get("author_id") or auth.is_admin(user.email))):
        p["content"] = ""
        p["locked"] = True
    p["comments"] = db.list_post_comments(p["id"])
    p["liked"] = db.user_liked_post(p["id"], user.id) if user else False
    return p


class UnlockRequest(BaseModel):
    password: str


@app.post("/api/blog/{post_id}/unlock")
def blog_unlock(post_id: int, req: UnlockRequest):
    if not db.check_post_password(post_id, req.password):
        raise HTTPException(403, "密碼錯誤")
    full = db.get_post(post_id)
    return {"ok": True, "content": (full or {}).get("content", "")}


@app.post("/api/blog/{post_id}/view")
def blog_view(post_id: int):
    return {"views": db.increment_post_views(post_id)}


@app.post("/api/blog/manage/{post_id}/preview-token")
def blog_preview_token(post_id: int, user=Depends(auth.get_current_user)):
    owner = db.post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "找不到文章")
    if owner != user.id and not auth.is_admin(user.email):
        raise HTTPException(403, "不是你的文章")
    return {"token": db.ensure_preview_token(post_id)}


@app.get("/api/blog/preview/{token}")
def blog_preview(token: str):
    p = db.get_post_by_preview_token(token)
    if not p:
        raise HTTPException(404, "預覽連結無效")
    p["preview"] = True
    return p


class AiWriteRequest(BaseModel):
    mode: str = "full"   # full | outline | refine
    topic: str = ""
    content: str = ""


@app.post("/api/blog/ai-write")
def blog_ai_write(req: AiWriteRequest, user=Depends(auth.get_current_user)):
    keys = db.get_settings(user.id)
    if req.mode == "outline":
        prompt = f"為主題「{req.topic}」用繁體中文寫一份結構化部落格大綱(H2/H3 標題 + 重點),Markdown 格式。"
    elif req.mode == "refine":
        prompt = f"用繁體中文潤飾、改善下面這篇文章,保留原意、讓行文更流暢專業,輸出 Markdown:\n\n{req.content[:6000]}"
    else:
        prompt = (f"用繁體中文寫一篇關於「{req.topic}」的完整部落格文章,Markdown 格式,"
                  "包含吸睛標題(# )、引言、數個 H2 段落與小結,內容具體實用。")
    text, model = ai.ai_complete(prompt, max_tokens=2000, user_keys=keys, user_id=user.id)
    if not text:
        raise HTTPException(400, "AI 暫時無法使用,請於後台設定 AI 金鑰")
    db.add_ai_chat_log(user.id, "blog_ai", f"[{req.mode}] {req.topic}", text)
    return {"content": text, "model": model}


class AiMetaRequest(BaseModel):
    title: str = ""
    content: str = ""


@app.post("/api/blog/ai-meta")
def blog_ai_meta(req: AiMetaRequest, user=Depends(auth.get_current_user)):
    keys = db.get_settings(user.id)
    prompt = ("根據以下文章,用繁體中文產生 SEO,只輸出 JSON(不要其他字):"
              '{"seo_title":"<60字內吸睛標題>","excerpt":"<120字內摘要>","tags":["標籤1","標籤2","標籤3"]}'
              f"\n\n標題:{req.title}\n內容:{req.content[:3000]}")
    text, _ = ai.ai_complete(prompt, max_tokens=400, user_keys=keys, user_id=user.id)
    if not text:
        raise HTTPException(400, "AI 暫時無法使用")
    import json as _json
    import re as _re
    try:
        m = _re.search(r"\{.*\}", text, _re.S)
        data = _json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    return {"seo_title": data.get("seo_title", ""), "excerpt": data.get("excerpt", ""), "tags": data.get("tags", [])}


class AiCoverRequest(BaseModel):
    title: str
    style: str = "插畫"


@app.post("/api/blog/ai-cover")
def blog_ai_cover(req: AiCoverRequest, user=Depends(auth.get_current_user)):
    import uploader
    if not uploader.r2_available():
        raise HTTPException(400, "尚未設定 R2 圖片儲存,無法保存生成的封面")
    keys = db.get_settings(user.id)
    prompt = f"部落格封面圖,主題:{req.title}。風格:{req.style}、乾淨、無文字、適合做標題圖。"
    data = ai.generate_image(prompt, user_keys=keys)
    if not data:
        raise HTTPException(400, "封面生成失敗(需 OpenAI 金鑰且帳號支援圖片生成)")
    url = uploader.upload(f"blog-cover-{user.id}.png", data, "image/png")
    db.add_ai_chat_log(user.id, "blog_cover", req.title, url)
    return {"url": url}


class CommentRequest(BaseModel):
    content: str
    parent_id: int | None = None


@app.post("/api/blog/{post_id}/like")
def blog_like(post_id: int, user=Depends(auth.get_current_user)):
    r = db.toggle_post_like(post_id, user.id)
    if not r.get("ok"):
        raise HTTPException(404, "找不到文章")
    return r


@app.get("/api/blog/{post_id}/comments")
def blog_comments(post_id: int):
    return {"comments": db.list_post_comments(post_id)}


@app.post("/api/blog/{post_id}/comments")
def blog_add_comment(post_id: int, req: CommentRequest, user=Depends(auth.get_current_user)):
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(400, "留言不能是空的")
    name = getattr(user, "username", "") or user.email.split("@")[0]
    return db.add_post_comment(post_id, user.id, name, content, req.parent_id)


@app.post("/api/blog/comment/{comment_id}/like")
def blog_comment_like(comment_id: int, user=Depends(auth.get_current_user)):
    r = db.toggle_comment_like(comment_id, user.id)
    if not r.get("ok"):
        raise HTTPException(404, "找不到留言")
    return r


@app.get("/api/blog/{post_id}/reactions")
def blog_get_reactions(post_id: int, user=Depends(auth.get_optional_user)):
    return db.get_reactions(post_id, user.id if user else None)


class ReactionRequest(BaseModel):
    emoji: str


@app.post("/api/blog/{post_id}/reactions")
def blog_react(post_id: int, req: ReactionRequest, user=Depends(auth.get_current_user)):
    return db.toggle_reaction(post_id, user.id, req.emoji[:8])


# ---- 後台:留言審核 + 精選 ----
@app.get("/api/admin/comments")
def admin_comments(admin=Depends(auth.get_admin)):
    return {"comments": db.admin_list_comments()}


class CommentStatusRequest(BaseModel):
    status: str  # visible | hidden | delete


@app.post("/api/admin/comments/{comment_id}/status")
def admin_comment_status(comment_id: int, req: CommentStatusRequest, request: Request, admin=Depends(auth.get_admin)):
    if not db.set_comment_status(comment_id, req.status):
        raise HTTPException(404, "找不到留言")
    db.log_audit(admin.email, f"comment_{req.status}", str(comment_id),
                 target_type="comment", ip=_ip(request))
    return {"ok": True}


class FeaturedRequest(BaseModel):
    featured: bool


@app.post("/api/admin/blog/{post_id}/featured")
def admin_blog_featured(post_id: int, req: FeaturedRequest, request: Request, admin=Depends(auth.get_admin)):
    if not db.set_post_featured(post_id, req.featured):
        raise HTTPException(404, "找不到文章")
    db.log_audit(admin.email, "post_featured" if req.featured else "post_unfeatured", str(post_id),
                 target_type="post", changes={"featured": req.featured}, ip=_ip(request))
    return {"ok": True}


@app.get("/api/admin/blog")
def admin_blog_list(admin=Depends(auth.get_admin)):
    return {"posts": db.list_all_posts()}


@app.get("/api/admin/blog/{post_id}")
def admin_blog_get(post_id: int, admin=Depends(auth.get_admin)):
    p = db.get_post(post_id)
    if not p:
        raise HTTPException(404, "找不到文章")
    return p


@app.post("/api/admin/blog")
def admin_blog_create(req: PostRequest, admin=Depends(auth.get_admin)):
    return db.create_post(admin.id, req.model_dump())


@app.put("/api/admin/blog/{post_id}")
def admin_blog_update(post_id: int, req: PostRequest, admin=Depends(auth.get_admin)):
    p = db.update_post(post_id, req.model_dump())
    if not p:
        raise HTTPException(404, "找不到文章")
    return p


@app.delete("/api/admin/blog/{post_id}")
def admin_blog_delete(post_id: int, admin=Depends(auth.get_admin)):
    if not db.delete_post(post_id):
        raise HTTPException(404, "找不到文章")
    return {"ok": True}


# ---------- 討論區 ----------

FORUM_CATEGORIES = [
    {"slug": "events", "label": "演唱會/活動", "emoji": "🎫"},
    {"slug": "merch", "label": "周邊", "emoji": "🧸"},
    {"slug": "anime", "label": "動漫", "emoji": "🎌"},
    {"slug": "game", "label": "遊戲", "emoji": "🎮"},
    {"slug": "tech", "label": "3C 科技", "emoji": "💻"},
    {"slug": "travel", "label": "旅遊", "emoji": "✈️"},
    {"slug": "photo", "label": "攝影", "emoji": "📷"},
    {"slug": "cooking", "label": "烹飪", "emoji": "🍳"},
    {"slug": "food", "label": "美食", "emoji": "🍜"},
    {"slug": "sport", "label": "運動", "emoji": "⚽"},
    {"slug": "pet", "label": "寵物", "emoji": "🐾"},
    {"slug": "fashion", "label": "時尚美妝", "emoji": "💄"},
    {"slug": "finance", "label": "理財投資", "emoji": "💰"},
    {"slug": "auto", "label": "汽機車", "emoji": "🚗"},
    {"slug": "media", "label": "影視音樂", "emoji": "🎬"},
    {"slug": "books", "label": "書籍", "emoji": "📚"},
    {"slug": "health", "label": "健康", "emoji": "🏥"},
    {"slug": "life", "label": "生活雜談", "emoji": "💬"},
]
_FORUM_SLUGS = {c["slug"] for c in FORUM_CATEGORIES}


class ThreadRequest(BaseModel):
    category: str
    title: str
    content: str = ""


class ReplyRequest(BaseModel):
    content: str


@app.get("/api/forum/categories")
def forum_categories():
    return {"categories": FORUM_CATEGORIES}


@app.get("/api/forum/threads")
def forum_threads(category: str | None = None):
    return {"threads": db.list_threads(category)}


@app.get("/api/forum/threads/{thread_id}")
def forum_thread(thread_id: int):
    t = db.get_thread(thread_id)
    if not t:
        raise HTTPException(404, "找不到主題")
    return t


@app.post("/api/forum/threads/{thread_id}/like")
def forum_like(thread_id: int):
    likes = db.like_thread(thread_id)
    return {"likes": likes}


@app.post("/api/forum/threads")
def forum_create_thread(req: ThreadRequest, user=Depends(auth.get_current_user)):
    if req.category not in _FORUM_SLUGS:
        raise HTTPException(400, "分類不存在")
    if not req.title.strip():
        raise HTTPException(400, "請輸入標題")
    return db.create_thread(user.id, user.email, req.category, req.title.strip(), req.content)


@app.post("/api/forum/threads/{thread_id}/replies")
def forum_reply(thread_id: int, req: ReplyRequest, user=Depends(auth.get_current_user)):
    if not req.content.strip():
        raise HTTPException(400, "請輸入內容")
    r = db.create_reply(thread_id, user.id, user.email, req.content.strip())
    if not r:
        raise HTTPException(404, "找不到主題")
    return r


@app.delete("/api/forum/threads/{thread_id}")
def forum_delete_thread(thread_id: int, user=Depends(auth.get_current_user)):
    if not db.delete_thread(thread_id, user.id, auth.is_admin(user.email)):
        raise HTTPException(404, "找不到主題或沒有權限")
    return {"ok": True}


@app.delete("/api/forum/replies/{reply_id}")
def forum_delete_reply(reply_id: int, user=Depends(auth.get_current_user)):
    if not db.delete_reply(reply_id, user.id, auth.is_admin(user.email)):
        raise HTTPException(404, "找不到回覆或沒有權限")
    return {"ok": True}
