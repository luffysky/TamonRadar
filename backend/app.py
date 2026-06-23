"""TamonRadar(多聞情報雷達) — FastAPI 後端。

把原本的 CLI 爬蟲包成 Web API:前端送關鍵字 → 背景爬 → SSE 即時回報 →
回傳結構化結果 → 提供篩選用資料、匯出、AI 摘要、歷史紀錄。
"""
import asyncio
import io
import json
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from crawler.config import CrawlConfig, DEFAULT_KEYWORDS
from crawler.reporter import to_dataframe, save_excel, save_markdown_report
import db
import auth
import notify
import scheduler
from oauth_google import router as google_router
from jobs import manager

app = FastAPI(title="TamonRadar API", version="2.0")
app.include_router(google_router)


@app.on_event("startup")
def _startup():
    db.init_db()
    scheduler.start()

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


class ChatRequest(BaseModel):
    run_id: str
    question: str


class AuthRequest(BaseModel):
    email: str
    password: str


class SettingsRequest(BaseModel):
    discord_webhook: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""


class ScheduleRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    provider: str = "brave"
    pages: int = 2
    max_detail: int = 0
    scrape_details: bool = False
    interval_hours: int = 24
    enabled: bool = True


# ---------- auth ----------

def _public_user(user) -> dict:
    return {"id": user.id, "email": user.email}


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
        user = db.User(email=email, password_hash=auth.hash_password(req.password))
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


# ---------- crawl ----------

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

def _anthropic():
    """回傳 (client, model) 或 None(沒金鑰/沒裝套件)。"""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    return Anthropic(api_key=key), os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


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


@app.post("/api/ai/chat")
def ai_chat(req: ChatRequest, user=Depends(auth.get_current_user)):
    records = _user_records(req.run_id, user)
    cli = _anthropic()
    if not cli:
        return {"available": False, "answer": "尚未設定 ANTHROPIC_API_KEY,無法使用 AI 對話。"}
    client, model = cli
    prompt = (
        "你是「多聞」周邊情報助理。根據以下 JSON 搜尋結果,用繁體中文回答使用者問題;"
        "提到具體商品時附上其連結與價格,答不出來就老實說資料裡沒有。\n\n"
        f"使用者問題:{req.question}\n\n資料:\n{json.dumps(_slim_records(records), ensure_ascii=False)}"
    )
    msg = client.messages.create(model=model, max_tokens=1500,
                                 messages=[{"role": "user", "content": prompt}])
    answer = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return {"available": True, "answer": answer}


@app.post("/api/ai/clean")
def ai_clean(req: SummarizeRequest, user=Depends(auth.get_current_user)):
    if not req.run_id:
        raise HTTPException(400, "請提供 run_id")
    records = _user_records(req.run_id, user)
    cli = _anthropic()
    if not cli:
        return {"available": False, "noise_urls": [], "message": "尚未設定 ANTHROPIC_API_KEY"}
    client, model = cli
    prompt = (
        "以下是一批「多聞」周邊的搜尋結果 JSON。請判斷哪些『不是真正的商品/情報頁』"
        "(例如純搜尋結果頁、空白頁、與多聞無關的雜訊)。\n"
        "只回傳 JSON,格式:{\"noise_urls\": [\"...\"]},不要其他文字。\n\n"
        f"資料:\n{json.dumps(_slim_records(records, 100), ensure_ascii=False)}"
    )
    msg = client.messages.create(model=model, max_tokens=1500,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    noise: list[str] = []
    try:
        start, end = text.find("{"), text.rfind("}")
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

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "available": False,
            "summary": "尚未設定 ANTHROPIC_API_KEY,無法產生 AI 摘要。請在後端環境變數設定後重試。",
        }

    try:
        from anthropic import Anthropic
    except ImportError:
        return {
            "available": False,
            "summary": "後端尚未安裝 anthropic 套件(pip install anthropic)。",
        }

    # 只餵必要欄位,控制 token
    slim = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "domain": r.get("domain", ""),
            "category": r.get("category", ""),
            "price": r.get("price", ""),
            "snippet": r.get("snippet", ""),
        }
        for r in records[:60]
    ]

    prompt = (
        "你是一個專門整理「多聞」相關情報的助理。以下是一批爬蟲抓到的搜尋結果(JSON)。\n"
        "請用繁體中文輸出 Markdown,包含:\n"
        "1. 整體重點摘要(3-5 點)\n"
        "2. 最值得關注的周邊/商品(含價格與連結,挑 5-8 個)\n"
        "3. 哪些可能是重複或雜訊資料\n"
        "4. 一句總結建議\n\n"
        f"資料:\n{json.dumps(slim, ensure_ascii=False)}"
    )

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    return {"available": True, "summary": text, "model": model}


# ---------- 通知設定 ----------

@app.get("/api/settings")
def get_settings(user=Depends(auth.get_current_user)):
    return db.get_settings(user.id)


@app.put("/api/settings")
def put_settings(req: SettingsRequest, user=Depends(auth.get_current_user)):
    db.save_settings(user.id, req.discord_webhook.strip(), req.telegram_token.strip(), req.telegram_chat_id.strip())
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
