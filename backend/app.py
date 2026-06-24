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
from fastapi.responses import Response
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


# ---------- auth ----------

def _public_user(user) -> dict:
    priv = bool(getattr(user, "privileged", False))
    return {
        "id": user.id,
        "email": user.email,
        "username": getattr(user, "username", "") or user.email.split("@")[0],
        "plan": "max" if priv else getattr(user, "plan", "free"),
        "privileged": priv,
        "is_admin": auth.is_admin(user.email),
    }


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
        return {"token": auth.create_token(user.id), "user": _public_user(user)}


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
        opts = data.get("data", {}).get("options", [])
        q = next((o.get("value", "") for o in opts if o.get("name") == "question"), "")
        bots.handle_discord_command_async(data.get("application_id"), data.get("token"), q)
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
    answer, _ = ai.ai_complete(prompt, max_tokens=900, **args)
    return {"available": True, "answer": answer}


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


@app.post("/api/crawl")
def start_crawl(req: CrawlRequest, user=Depends(auth.get_current_user)):
    config = CrawlConfig(
        keywords=req.keywords,
        google_pages_per_keyword=req.google_pages_per_keyword,
        max_detail_pages=req.max_detail_pages,
        headless=req.headless,
        scrape_details=req.scrape_details,
        search_provider=req.search_provider or CrawlConfig().search_provider,
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


@app.post("/api/ai/chat")
def ai_chat(req: ChatRequest, user=Depends(auth.get_current_user)):
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
    answer, model = ai.ai_complete(prompt, max_tokens=1500, **args)
    db.bump_ai_usage(user.id)
    return {"available": True, "answer": answer, "model": model}


@app.post("/api/ai/compare")
def ai_compare(req: CompareRequest, user=Depends(auth.get_current_user)):
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
    answer, _ = ai.ai_complete(prompt, max_tokens=1500, **args)
    db.bump_ai_usage(user.id)
    return {"available": True, "answer": answer}


@app.post("/api/ai/keywords")
def ai_keywords(req: KeywordsRequest, user=Depends(auth.get_current_user)):
    args = _ai_args(user)
    if not ai.ai_available(**args):
        return {"available": False, "keywords": []}
    prompt = (
        "把以下需求展開成 5-8 個適合在購物/搜尋引擎使用的繁體中文關鍵字。"
        "只回 JSON 字串陣列,不要其他文字。\n需求:" + req.query
    )
    text, _ = ai.ai_complete(prompt, max_tokens=300, **args)
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
    prompt = (
        "以下是一批網路搜尋結果 JSON。請判斷哪些是『沒有實質內容的雜訊』"
        "(例如純搜尋結果頁、空白/錯誤頁、與搜尋主題明顯無關的內容)。\n"
        "只回傳 JSON,格式:{\"noise_urls\": [\"...\"]},不要其他文字。\n\n"
        f"資料:\n{json.dumps(_slim_records(records, 100), ensure_ascii=False)}"
    )
    text, _ = ai.ai_complete(prompt, max_tokens=1500, **args)
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
    text, model = ai.ai_complete(prompt, max_tokens=2000, **args)
    db.bump_ai_usage(user.id)
    return {"available": True, "summary": text, "model": model}


# ---------- 通知設定 ----------

@app.get("/api/settings")
def get_settings(user=Depends(auth.get_current_user)):
    return db.get_settings(user.id)


@app.put("/api/settings")
def put_settings(req: SettingsRequest, user=Depends(auth.get_current_user)):
    db.save_settings(user.id, {
        "discord_webhook": req.discord_webhook.strip(),
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
    return {"ok": True}


class PrivilegeRequest(BaseModel):
    privileged: bool


@app.post("/api/admin/users/{user_id}/privilege")
def admin_set_privilege(user_id: int, req: PrivilegeRequest, admin=Depends(auth.get_admin)):
    if not db.set_privilege(user_id, req.privileged):
        raise HTTPException(404, "找不到使用者")
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
    tags: list[str] = Field(default_factory=list)
    published: bool = False


@app.get("/api/blog")
def blog_list(category: str | None = None):
    return {"posts": db.list_published_posts(category)}


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


@app.post("/api/blog")
def blog_create(req: PostRequest, user=Depends(auth.get_current_user)):
    return db.create_post(user.id, req.model_dump())


@app.put("/api/blog/{post_id}")
def blog_update(post_id: int, req: PostRequest, user=Depends(auth.get_current_user)):
    owner = db.post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "找不到文章")
    if owner != user.id and not auth.is_admin(user.email):
        raise HTTPException(403, "不是你的文章")
    return db.update_post(post_id, req.model_dump())


@app.delete("/api/blog/{post_id}")
def blog_delete(post_id: int, user=Depends(auth.get_current_user)):
    owner = db.post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "找不到文章")
    if owner != user.id and not auth.is_admin(user.email):
        raise HTTPException(403, "不是你的文章")
    db.delete_post(post_id)
    return {"ok": True}


@app.get("/api/blog/{slug}")
def blog_get(slug: str):
    p = db.get_post_by_slug(slug)
    if not p:
        raise HTTPException(404, "找不到文章")
    return p


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
