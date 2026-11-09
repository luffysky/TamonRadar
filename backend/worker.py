"""工作者:由 Vercel Cron 每分鐘呼叫,或建立工作時立即自我觸發。

在時間預算內反覆認領並執行工作。沒認領到就直接結束。觸發遺失只會多等下一次 cron。
"""
import os
import time
import traceback
import uuid

import requests
from sqlalchemy import delete, select

from crawler.config import BudgetExhausted
from crawler.runner import run_crawl
from crawler.site_crawler import run_site_crawl
import bots
import db
import jobs
import ratelimit
import scheduler
import watcher

DEFAULT_BUDGET = 240.0   # 遠低於 Function 上限 800 秒;超過預算的工作會放回佇列由下一輪接續
MIN_SLICE = 5.0           # 剩不到這麼多秒就不再認領新工作

EVENT_RETENTION_DAYS = int(os.environ.get("JOB_EVENT_RETENTION_DAYS", "7"))
JOB_RETENTION_DAYS = int(os.environ.get("JOB_RETENTION_DAYS", "30"))
SYSTEM_JOB_RETENTION_DAYS = int(os.environ.get("SYSTEM_JOB_RETENTION_DAYS", "3"))
PRICE_RETENTION_DAYS = int(os.environ.get("PRICE_OBSERVATION_RETENTION_DAYS", "365"))


def _budget() -> float:
    try:
        return float(os.environ.get("WORKER_BUDGET_SECONDS", DEFAULT_BUDGET))
    except ValueError:
        return DEFAULT_BUDGET


def _base_url() -> str:
    explicit = (os.environ.get("WORKER_TRIGGER_BASE") or "").strip().rstrip("/")
    if explicit:
        return explicit
    host = (os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL") or "").strip()
    return f"https://{host}" if host else ""


def trigger(connect_timeout: float = 1.5, read_timeout: float = 0.5) -> bool:
    """盡力而為地叫醒一個工作者(不等待結果)。遺失只會延後到下一次 cron,不影響正確性。"""
    base = _base_url()
    secret = (os.environ.get("CRON_SECRET") or "").strip()
    if not base or not secret:
        return False
    try:
        requests.post(f"{base}/api/internal/worker", headers={"Authorization": f"Bearer {secret}"},
                      timeout=(connect_timeout, read_timeout))
        return True
    except requests.exceptions.ReadTimeout:
        return True   # 請求已送達,工作者在另一個呼叫裡繼續跑
    except Exception as e:
        print(f"[worker] 自我觸發失敗,等待下一次 cron:{e}")
        return False


# ---------- 各類工作 ----------

def _run_crawl(h: jobs.JobHandle) -> None:
    config = jobs.config_from_dict(h.config)
    result = run_crawl(config, on_event=h.add_event, should_stop=h.should_stop, cursor=h.cursor or None,
                       checkpoint=h.checkpoint, budget_left=h.budget_left)
    h.finish("stopped" if h.should_stop() else "done", result=result, keywords=config.keywords)


def _run_site_crawl(h: jobs.JobHandle) -> None:
    config = jobs.config_from_dict(h.config)
    result = run_site_crawl(config, on_event=h.add_event, should_stop=h.should_stop,
                            store=jobs.DbSiteStore(h), budget_left=h.budget_left)
    h.finish("stopped" if h.should_stop() else "done", result=result, keywords=config.keywords)


def _run_watch(h: jobs.JobHandle) -> None:
    watcher.check_watch(h.config["watch_id"])
    h.finish("done", save_run=False)


def _run_favorites(h: jobs.JobHandle) -> None:
    # 到期的收藏以 last_checked 判斷,預算用完下一輪掃描自然接續,不需要 cursor
    watcher.check_due_favorites(budget_left=h.keepalive)
    h.finish("done", save_run=False)


def _run_digest(h: jobs.JobHandle) -> None:
    scheduler._daily_digest(h)
    h.finish("done", save_run=False)


def _run_broadcast(h: jobs.JobHandle) -> None:
    if not h.cursor.get("started"):   # 已開始送過就不重送(沿用「先認領再寄」的至多一次語意)
        h.checkpoint({"started": True})
        db.send_broadcast(h.config["broadcast_id"], on_tick=h.keepalive)
    h.finish("done", save_run=False)


def _run_bot(h: jobs.JobHandle) -> None:
    if h.kind == "bot_telegram":
        bots.run_telegram(h.config)
    else:
        bots.run_discord(h.config)
    h.finish("done", save_run=False)


def _run_maintenance(h: jobs.JobHandle) -> None:
    from datetime import timedelta
    now = db._now()
    counts = {"rate_limits": ratelimit.purge_expired()}
    with db.SessionLocal() as s:
        counts["events"] = s.execute(delete(db.JobEvent).where(
            db.JobEvent.created_at < now - timedelta(days=EVENT_RETENTION_DAYS))).rowcount
        # 已結束的系統型工作留短一點(監看每次都產生一筆)
        system = ("watch", "favorites", "digest", "broadcast", "maintenance", "bot_telegram", "bot_discord")
        old_system = list(s.scalars(select(db.Job.id).where(
            db.Job.status.in_(jobs.TERMINAL), db.Job.kind.in_(system),
            db.Job.finished_at < now - timedelta(days=SYSTEM_JOB_RETENTION_DAYS)).limit(5000)).all())
        old_jobs = list(s.scalars(select(db.Job.id).where(
            db.Job.status.in_(jobs.TERMINAL), db.Job.kind.in_(jobs.CRAWL_KINDS),
            db.Job.finished_at < now - timedelta(days=JOB_RETENTION_DAYS)).limit(5000)).all())
        ids = old_system + old_jobs
        if ids:
            s.execute(delete(db.JobEvent).where(db.JobEvent.job_id.in_(ids)))
            s.execute(delete(db.CrawlFrontier).where(db.CrawlFrontier.job_id.in_(ids)))
            s.execute(delete(db.Job).where(db.Job.id.in_(ids)))
        counts["jobs"] = len(ids)
        counts["price_observations"] = s.execute(delete(db.PriceObservation).where(
            db.PriceObservation.observed_at < now - timedelta(days=PRICE_RETENTION_DAYS))).rowcount
        s.commit()
    print(f"[maintenance] {counts}")
    h.finish("done", save_run=False)


HANDLERS = {
    "crawl": _run_crawl,
    "site_crawl": _run_site_crawl,
    "schedule": scheduler.run_schedule_job,
    "watch": _run_watch,
    "favorites": _run_favorites,
    "digest": _run_digest,
    "broadcast": _run_broadcast,
    "bot_telegram": _run_bot,
    "bot_discord": _run_bot,
    "maintenance": _run_maintenance,
}


def execute(h: jobs.JobHandle) -> None:
    if h.cursor and h.kind in jobs.CRAWL_KINDS:
        h.add_event({"type": "info", "message": "從上次進度繼續…"})
    try:
        HANDLERS[h.kind](h)
        if not h.finished:
            h.finish("done", save_run=False)
    except BudgetExhausted:
        h.requeue()
    except jobs.LostClaim:
        print(f"[worker] {h.id} 已被其他工作者接手,放棄這一輪")
    except Exception as e:
        print(f"[worker] {h.id} ({h.kind}) 失敗:{e}\n{traceback.format_exc()}")
        message = str(e) or e.__class__.__name__
        h.add_event({"type": "error", "message": f"爬蟲發生錯誤:{message}"[:500]})
        try:
            h.finish("error", error=message)
        except jobs.LostClaim:
            pass


def run(budget: float | None = None, max_jobs: int | None = None) -> dict:
    budget = _budget() if budget is None else budget
    started = time.monotonic()
    deadline = started + budget
    worker_id = uuid.uuid4().hex[:10]
    processed: list[dict] = []
    while time.monotonic() + MIN_SLICE < deadline and (max_jobs is None or len(processed) < max_jobs):
        h = jobs.claim_next(worker_id, deadline)
        if h is None:
            break
        execute(h)
        processed.append({"id": h.id, "kind": h.kind})
    return {"processed": len(processed), "jobs": processed, "elapsed": round(time.monotonic() - started, 2)}


def run_job(job_id: str | None, budget: float | None = None) -> None:
    """同步跑完指定工作(本機/測試用)。"""
    if not job_id:
        return
    h = jobs.claim_next(uuid.uuid4().hex[:10], time.monotonic() + (budget if budget is not None else _budget()),
                        job_id=job_id)
    if h is not None:
        execute(h)
