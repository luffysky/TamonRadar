"""排程:定時自動爬蟲,跑完跟上次比較,有變化就推播給使用者。"""
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from crawler.config import CrawlConfig
from crawler.runner import run_crawl
import db
import jobs
import notify
import quota
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
    # 每日彙整(01:00 UTC ≈ 台灣 09:00)
    _sched.add_job(_daily_digest, "cron", hour=1, minute=0, id="daily-digest", replace_existing=True)
    # 每分鐘檢查到期的排程推播
    _sched.add_job(_run_due_broadcasts, "interval", minutes=1, id="due-broadcasts", replace_existing=True)
    # 目標價收藏:每 15 分鐘掃一次到期的(同一個收藏最短間隔見 watcher.FAVORITE_RECHECK_MINUTES)
    _sched.add_job(watcher.check_due_favorites, "interval", minutes=15, id="favorite-targets",
                   replace_existing=True, max_instances=1, coalesce=True)


def _run_due_broadcasts() -> None:
    try:
        db.run_due_broadcasts()
    except Exception as e:
        print(f"[scheduler] 排程推播失敗:{e}")


def _daily_digest() -> None:
    for uid in db.list_digest_user_ids():
        settings = db.get_settings(uid)
        has_channel = notify.has_channel(settings)
        favs = db.list_favorites(uid)
        watches = db.list_watches(uid)
        avail = [w for w in watches if w.get("last_status") == "available"]
        lines = [f"收藏 {len(favs)} 項、監看 {len(watches)} 項。"]
        if avail:
            lines.append("✅ 目前可購買的監看:")
            for w in avail[:10]:
                lines.append(f"・{w['name'] or w['url']}")
        body = "\n".join(lines)
        db.add_notification(uid, "📬 每日彙整", body)  # 站內一定存
        if has_channel:
            try:
                notify.notify_all(settings, "📬 TamonRadar 每日彙整\n" + body)
            except Exception:
                pass


def _job_id(schedule_id: int) -> str:
    return f"sch-{schedule_id}"


def _add(sc: dict) -> None:
    _sched.add_job(
        _run, "interval",
        hours=max(quota.caps_for_id(sc["user_id"]).min_schedule_hours, int(sc["interval_hours"])),
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
        minutes=max(quota.caps_for_id(w["user_id"]).min_watch_minutes, int(w["interval_minutes"])),
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

    # 排程也算搜尋用量;額度用完就跳過這次並告知使用者
    try:
        quota.enforce_by_id(sc["user_id"], "search")
    except quota.QuotaExceeded as e:
        db.add_notification(sc["user_id"], "📡 排程略過", e.message)
        return

    caps = quota.caps_for_id(sc["user_id"])
    config = CrawlConfig(
        keywords=sc["keywords"][:caps.keywords],
        google_pages_per_keyword=min(sc["pages"], caps.pages),
        max_detail_pages=min(sc["max_detail"], caps.detail_pages),
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
    _msg = _build_message(sc, result, prev)
    db.add_notification(sc["user_id"], f"📡 排程更新:{'、'.join(sc['keywords'])[:40]}", _msg)
    if notify.has_channel(settings):
        notify.notify_all(settings, _msg)
