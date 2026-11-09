"""排程派發器:每分鐘由 Vercel Cron 呼叫一次,把到期的排程/監看/推播/彙整原子地轉成工作。

每一項都用 next_run_at + FOR UPDATE SKIP LOCKED 在同一個交易裡「推進下次時間 + 建立工作」,
所以重疊或重試的 cron 都不會重複觸發,服務重啟也不會把全部重跑一次。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from crawler.config import CrawlConfig
from crawler.runner import run_crawl
import db
import jobs
import notify
import quota
import radar
import watcher

BATCH = 200
CLAIM_LEASE = timedelta(minutes=30)   # 認領後工作一直沒結束時,超過這段時間才允許再派一次
FAVORITES_EVERY = timedelta(minutes=15)
MAINTENANCE_EVERY = timedelta(hours=1)
DIGEST_HOUR_UTC = 1   # 01:00 UTC ≈ 台灣 09:00


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _next_digest(now: datetime) -> datetime:
    at = now.replace(hour=DIGEST_HOUR_UTC, minute=0, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def _caps(s, user_id: int) -> tuple[quota.Caps, bool]:
    user = s.get(db.User, user_id)
    return (quota.caps_for(user) if user is not None else quota.FREE_CAPS), bool(user is None or user.banned)


def _dispatch_rows(s, model, now: datetime, interval_of, kind: str, id_field: str) -> int:
    """推進到期列的 next_run_at 並建立工作;在同一個交易內完成。"""
    # 尚未有下次時間(剛匯入舊資料)→ 依上次執行推算,不要全部一次爆發
    last_field = model.last_run if model is db.Schedule else model.last_checked
    for row in s.scalars(select(model).where(model.enabled == True, model.next_run_at.is_(None))  # noqa: E712
                         .with_for_update(skip_locked=True).limit(BATCH)).all():
        caps, _banned = _caps(s, row.user_id)
        base = _aware(getattr(row, last_field.key))
        row.next_run_at = max(now, base + interval_of(row, caps)) if base else now
    s.flush()

    due = s.scalars(
        select(model)
        .where(model.enabled == True, model.next_run_at <= now,  # noqa: E712
               or_(model.claimed_at.is_(None), model.claimed_at < now - CLAIM_LEASE))
        .order_by(model.next_run_at).limit(BATCH).with_for_update(skip_locked=True)
    ).all()
    fired = 0
    for row in due:
        caps, banned = _caps(s, row.user_id)
        fire_at = _aware(row.next_run_at)
        row.next_run_at = now + interval_of(row, caps)
        if banned:
            continue
        jid = jobs._add_job(s, kind, user_id=row.user_id, config={id_field: row.id},
                            dedupe_key=f"{kind}:{row.id}:{int(fire_at.timestamp())}",
                            max_attempts=3 if kind == "schedule" else 2)
        if jid:
            row.claimed_at = now
            row.claim_job_id = jid
            fired += 1
    return fired


def _schedule_interval(sc, caps: quota.Caps) -> timedelta:
    return timedelta(hours=max(caps.min_schedule_hours, int(sc.interval_hours)))


def _watch_interval(w, caps: quota.Caps) -> timedelta:
    return timedelta(minutes=max(caps.min_watch_minutes, int(w.interval_minutes)))


def _dispatch_broadcasts(s, now: datetime) -> int:
    fired = 0
    for bid in db.due_broadcast_ids(s, now, lock=True):
        s.execute(update(db.ScheduledBroadcast).where(db.ScheduledBroadcast.id == bid).values(sent=True))
        if jobs._add_job(s, "broadcast", config={"broadcast_id": bid}, dedupe_key=f"broadcast:{bid}", max_attempts=1):
            fired += 1
    return fired


def _claim_singleton(s, name: str, now: datetime, next_at: datetime, first_at: datetime | None = None) -> bool:
    """全站單例排程:UPDATE ... WHERE next_run_at <= now 只有一個交易會成功。"""
    s.execute(db.dialect_insert(db.CronState).values(name=name, next_run_at=first_at or now)
              .on_conflict_do_nothing(index_elements=["name"]))
    return s.execute(update(db.CronState).where(db.CronState.name == name, db.CronState.next_run_at <= now)
                     .values(next_run_at=next_at, last_run_at=now)).rowcount == 1


def _dispatch_singletons(s, now: datetime) -> dict:
    out = {}
    if _claim_singleton(s, "daily_digest", now, _next_digest(now), first_at=_next_digest(now)):
        out["digest"] = bool(jobs._add_job(s, "digest", dedupe_key=f"digest:{now:%Y-%m-%d}"))
    if _claim_singleton(s, "favorites", now, now + FAVORITES_EVERY):
        out["favorites"] = bool(jobs._add_job(s, "favorites", max_attempts=1))
    if _claim_singleton(s, "maintenance", now, now + MAINTENANCE_EVERY):
        out["maintenance"] = bool(jobs._add_job(s, "maintenance", max_attempts=1))
    return out


def fired_anything(counts: dict) -> bool:
    for v in counts.values():
        if isinstance(v, dict) and any(v.values()):
            return True
        if isinstance(v, int) and v:
            return True
    return False


def dispatch(now: datetime | None = None) -> dict:
    """派發一輪;各類別各自一個交易,一類失敗不影響其他類。"""
    now = now or db._now()
    counts: dict = {}
    steps = (
        ("schedules", lambda s: _dispatch_rows(s, db.Schedule, now, _schedule_interval, "schedule", "schedule_id")),
        ("watches", lambda s: _dispatch_rows(s, db.Watch, now, _watch_interval, "watch", "watch_id")),
        ("broadcasts", lambda s: _dispatch_broadcasts(s, now)),
        ("singletons", lambda s: _dispatch_singletons(s, now)),
    )
    for name, fn in steps:
        try:
            with db.SessionLocal() as s:
                counts[name] = fn(s)
                s.commit()
        except Exception as e:
            print(f"[dispatch] {name} 失敗:{e}")
            counts[name] = f"error: {str(e)[:120]}"
    return counts


# ---------- 工作處理(由 worker 呼叫)----------

def _daily_digest(handle=None) -> None:
    done_up_to = int((handle.cursor if handle else {}).get("after_uid", 0))
    for uid in sorted(db.list_digest_user_ids()):
        if uid <= done_up_to:
            continue
        if handle is not None and not handle.keepalive():
            raise jobs.BudgetExhausted()
        if handle is not None:
            handle.checkpoint({"after_uid": uid})   # 先記再寄:崩潰時寧可少寄一人,不重複寄
        settings = db.get_settings(uid)
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
        if notify.has_channel(settings):
            try:
                notify.notify_all(settings, "📬 TamonRadar 每日彙整\n" + body)
            except Exception:
                pass


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


def run_schedule_job(h) -> None:
    """排程工作:扣額度 → 爬(可續跑)→ 存歷史 → 通知(先記 notified 再發,崩潰也不重發)。"""
    sc = db.get_schedule(h.config["schedule_id"])
    if not sc or (not sc.get("enabled") and not h.config.get("manual")):
        h.finish("done", save_run=False)
        return

    state = dict(h.cursor)
    if not state.get("charged"):
        # 排程也算搜尋用量;額度用完就跳過這次並告知使用者
        try:
            quota.enforce_by_id(sc["user_id"], "search")
        except quota.QuotaExceeded as e:
            db.add_notification(sc["user_id"], "📡 排程略過", e.message)
            h.finish("done", save_run=False)
            return
        state["charged"] = True
        h.checkpoint(state)

    if not state.get("saved"):
        caps = quota.caps_for_id(sc["user_id"])
        config = CrawlConfig(
            keywords=sc["keywords"][:caps.keywords],
            google_pages_per_keyword=min(sc["pages"], caps.pages),
            max_detail_pages=min(sc["max_detail"], caps.detail_pages),
            scrape_details=sc["scrape_details"],
            search_provider=sc["provider"],
        )
        result = run_crawl(
            config, on_event=h.add_event, should_stop=h.should_stop, cursor=state.get("crawl"),
            checkpoint=lambda c: h.checkpoint({**state, "crawl": c}), budget_left=h.budget_left,
        )
        # 抓上次結果供比較(在寫入新結果之前)
        prev = db.previous_run(sc["user_id"], db._now().isoformat(), h.id, sc["keywords"])
        db.upsert_run(h.id, sc["user_id"], "done", sc["keywords"], result)
        db.touch_schedule(sc["id"])
        state = {"charged": True, "saved": True, "message": _build_message(sc, result, prev)}
        h.checkpoint(state)

    if not state.get("notified"):
        msg = state.get("message", "")
        state["notified"] = True
        h.checkpoint(state)
        settings = db.get_settings(sc["user_id"])
        db.add_notification(sc["user_id"], f"📡 排程更新:{'、'.join(sc['keywords'])[:40]}", msg)
        if notify.has_channel(settings):
            notify.notify_all(settings, msg)

    h.finish("done", save_run=False)


def enqueue_schedule_run(schedule_id: int, user_id: int) -> str | None:
    return jobs.enqueue("schedule", user_id=user_id, config={"schedule_id": schedule_id, "manual": True}, priority=3)


def enqueue_watch_check(watch_id: int, user_id: int) -> str | None:
    return jobs.enqueue("watch", user_id=user_id, config={"watch_id": watch_id}, priority=3, max_attempts=2)


def _run(schedule_id: int) -> None:
    """同步跑一次指定排程(本機/測試用)。"""
    import worker
    sc = db.get_schedule(schedule_id)
    if not sc:
        return
    worker.run_job(enqueue_schedule_run(schedule_id, sc["user_id"]))
