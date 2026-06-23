"""排程:定時自動爬蟲,跑完跟上次比較,有變化就推播給使用者。"""
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from crawler.config import CrawlConfig
from crawler.runner import run_crawl
import db
import jobs
import notify
import radar
import watcher

_sched = BackgroundScheduler(timezone="UTC")
_started = False


def start() -> None:
    global _started
    if _started:
        return
    _sched.start()
    _started = True
    for sc in db.list_enabled_schedules():
        _add(sc)
    for w in db.list_enabled_watches():
        add_watch(w)


def _job_id(schedule_id: int) -> str:
    return f"sch-{schedule_id}"


def _add(sc: dict) -> None:
    _sched.add_job(
        _run, "interval",
        hours=max(1, int(sc["interval_hours"])),
        id=_job_id(sc["id"]),
        args=[sc["id"]],
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),  # 建立後很快先跑一次
    )


def sync(sc: dict) -> None:
    """建立/更新排程後呼叫:依 enabled 加入或移除。"""
    remove(sc["id"])
    if sc.get("enabled"):
        _add(sc)


def remove(schedule_id: int) -> None:
    try:
        _sched.remove_job(_job_id(schedule_id))
    except Exception:
        pass


def run_now(schedule_id: int) -> None:
    _run(schedule_id)


# ---------- 監看任務 ----------

def _watch_job_id(watch_id: int) -> str:
    return f"watch-{watch_id}"


def add_watch(w: dict) -> None:
    _sched.add_job(
        watcher.check_watch, "interval",
        minutes=max(1, int(w["interval_minutes"])),
        id=_watch_job_id(w["id"]),
        args=[w["id"]],
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),
    )


def sync_watch(w: dict) -> None:
    remove_watch(w["id"])
    if w.get("enabled"):
        add_watch(w)


def remove_watch(watch_id: int) -> None:
    try:
        _sched.remove_job(_watch_job_id(watch_id))
    except Exception:
        pass


def check_watch_now(watch_id: int) -> None:
    watcher.check_watch(watch_id)


def _build_message(sc: dict, result: dict, prev: dict | None) -> str:
    s = result.get("summary", {})
    lines = [
        "📡 TamonRadar 排程更新",
        f"關鍵字:{'、'.join(sc['keywords'])}",
        f"共 {s.get('total', 0)} 筆,有價格 {s.get('with_price', 0)} 筆",
    ]
    if prev:
        d = radar.compute_diff(result.get("records", []), prev.get("records", []))
        c = d["counts"]
        lines.append(f"📊 新品 {c['new']} / 降價 {c['price_drops']} / 補貨 {c['restock']}")
        for it in d["price_drops"][:5]:
            lines.append(f"💰 {it['title']} {it.get('old_price','')}→{it['price']} (↓{it['drop_pct']}%)")
        for it in d["new_items"][:5]:
            lines.append(f"✨ {it['title']} {it.get('price','')}")
    return "\n".join(lines)


def _run(schedule_id: int) -> None:
    sc = db.get_schedule(schedule_id)
    if not sc or not sc.get("enabled"):
        remove(schedule_id)
        return

    config = CrawlConfig(
        keywords=sc["keywords"],
        google_pages_per_keyword=sc["pages"],
        max_detail_pages=sc["max_detail"],
        scrape_details=sc["scrape_details"],
        search_provider=sc["provider"],
    )

    # 抓上次結果供比較(在寫入新結果之前)
    prev_runs = db.list_runs(sc["user_id"])
    prev = db.get_run(prev_runs[0]["id"], sc["user_id"]) if prev_runs else None

    jobs._slots.acquire()
    try:
        result = run_crawl(config)
    except Exception:
        jobs._slots.release()
        return
    jobs._slots.release()

    run_id = uuid.uuid4().hex[:12]
    db.create_run_record(sc["user_id"], run_id, sc["keywords"], result)
    db.touch_schedule(schedule_id)

    settings = db.get_settings(sc["user_id"])
    has_channel = settings.get("discord_webhook") or (
        settings.get("telegram_token") and settings.get("telegram_chat_id")
    )
    if has_channel:
        notify.notify_all(settings, _build_message(sc, result, prev))
