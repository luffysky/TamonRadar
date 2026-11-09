"""雷達比對範圍、通知管道、目標價、刪除路徑、資料遺失、廣播。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

import db
import notify
import scheduler
import watcher
from crawler import runner
from crawler.config import CrawlConfig
from jobs import manager

# ---------- 雷達 ----------


def add_run(user_id, rid, keywords, finished, status="done", records=None):
    with db.SessionLocal() as s:
        s.add(db.Run(id=rid, user_id=user_id, status=status, keywords=keywords, summary={}, records=records or [],
                     finished_at=finished, created_at=finished))
        s.commit()


T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LATER = (T0 + timedelta(days=1)).isoformat()


def test_previous_run_scoped_to_keywords(make_user):
    u = make_user()
    add_run(u.id, "cats", ["貓砂"], T0)
    add_run(u.id, "dogs", ["狗糧"], T0 + timedelta(hours=1))
    assert db.previous_run(u.id, LATER, "", ["貓砂"])["id"] == "cats"


def test_previous_run_none_when_unrelated(make_user):
    u = make_user()
    add_run(u.id, "dogs", ["狗糧"], T0)
    assert db.previous_run(u.id, LATER, "", ["貓砂"]) is None


def test_previous_run_matches_on_overlap_case_insensitive(make_user):
    u = make_user()
    add_run(u.id, "r1", ["GPU", "顯卡"], T0)
    assert db.previous_run(u.id, LATER, "", [" gpu "])["id"] == "r1"


def test_previous_run_no_keywords_returns_none(make_user):
    u = make_user()
    add_run(u.id, "r1", ["GPU"], T0)
    assert db.previous_run(u.id, LATER, "", []) is None


def test_previous_run_skips_failed_and_self_and_other_users(make_user):
    u, v = make_user(), make_user()
    add_run(u.id, "failed", ["k"], T0, status="error")
    add_run(u.id, "self", ["k"], T0 + timedelta(hours=1))
    add_run(v.id, "theirs", ["k"], T0 + timedelta(hours=2))
    assert db.previous_run(u.id, LATER, "self", ["k"]) is None


def test_history_diff_ignores_unrelated_run(client, make_user, bearer):
    u = make_user()
    add_run(u.id, "old", ["狗糧"], T0, records=[{"title": "A", "url": "u", "price": "NT$100"}])
    add_run(u.id, "new", ["貓砂"], T0 + timedelta(hours=1), records=[{"title": "B", "url": "v", "price": "NT$50"}])
    assert client.get("/api/history/new/diff", headers=bearer(u)).json() == {"has_previous": False}


def test_scheduled_run_compares_same_keywords(make_user, monkeypatch):
    u = make_user()
    add_run(u.id, "unrelated", ["狗糧"], T0 + timedelta(hours=5), records=[{"title": "狗", "url": "d", "price": "NT$9"}])
    add_run(u.id, "related", ["貓砂"], T0, records=[{"title": "貓", "url": "c", "price": "NT$100"}])
    sc = db.create_schedule(u.id, {"keywords": ["貓砂"], "enabled": True, "provider": "duckduckgo"})
    seen = {}
    monkeypatch.setattr(scheduler, "run_crawl", lambda c, **k: {"records": [], "summary": {}})
    monkeypatch.setattr(scheduler, "_build_message", lambda sc, result, prev: seen.update(prev=prev) or "msg")
    scheduler._run(sc["id"])
    assert seen["prev"]["id"] == "related"


# ---------- 通知管道 ----------

@pytest.mark.parametrize("settings,env,expected", [
    ({"discord_webhook": "https://discord.com/api/webhooks/1/a"}, {}, True),
    ({"telegram_token": "t", "telegram_chat_id": "1"}, {}, True),
    ({"telegram_chat_id": "1"}, {"TELEGRAM_BOT_TOKEN": "central"}, True),
    ({"discord_user_id": "9"}, {"DISCORD_BOT_TOKEN": "central"}, True),
    ({"telegram_chat_id": "1"}, {}, False),
    ({"discord_user_id": "9"}, {}, False),
    ({}, {"TELEGRAM_BOT_TOKEN": "central"}, False),
])
def test_has_channel(monkeypatch, settings, env, expected):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert notify.has_channel(settings) is expected


def test_scheduled_alert_reaches_bound_user(make_user, monkeypatch):
    u = make_user()
    db.save_settings(u.id, {"telegram_chat_id": "123"})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "central")
    sc = db.create_schedule(u.id, {"keywords": ["k"], "enabled": True, "provider": "duckduckgo"})
    sent = []
    monkeypatch.setattr(scheduler, "run_crawl", lambda c, **k: {"records": [], "summary": {}})
    monkeypatch.setattr(notify, "notify_all", lambda st, text, embed=None: sent.append(text) or {})
    scheduler._run(sc["id"])
    assert len(sent) == 1


def test_daily_digest_reaches_bound_user(make_user, monkeypatch):
    u = make_user()
    db.save_settings(u.id, {"discord_user_id": "9", "daily_digest": True})
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "central")
    sent = []
    monkeypatch.setattr(notify, "notify_all", lambda st, text, embed=None: sent.append(text) or {})
    scheduler._daily_digest()
    assert len(sent) == 1


# ---------- 收藏目標價 ----------

def page(price="NT$100", status=200):
    html = f'<head><meta property="og:price:amount" content="{price}"></head><body>x</body>'
    return SimpleNamespace(status_code=status, text=html, headers={})


@pytest.fixture
def fav(make_user):
    u = make_user()
    f = db.add_favorite(u.id, {"url": "https://shop.example.com/a", "title": "商品"})
    return db.set_favorite_target(f["id"], u.id, 500)


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(notify, "notify_all", lambda st, text, embed=None: out.append(text) or {})
    return out


def fresh(fav):
    return next(f for f in db.list_due_favorites(datetime.now(timezone.utc) + timedelta(days=1)) if f["id"] == fav["id"])


def test_favorite_target_fires_without_any_crawl(monkeypatch, fav, sent):
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$450"))
    db.save_settings(fav["user_id"], {"telegram_chat_id": "1", "telegram_token": "t"})
    res = watcher.check_favorite(fresh(fav))
    assert res["notified"] is True and len(sent) == 1
    assert db.list_notifications(fav["user_id"])["items"][0]["title"] == "🎯 目標價通知"


def test_favorite_target_fires_once_until_price_rises(monkeypatch, fav, sent):
    db.save_settings(fav["user_id"], {"telegram_chat_id": "1", "telegram_token": "t"})
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$450"))
    watcher.check_favorite(fresh(fav))
    watcher.check_favorite(fresh(fav))
    assert len(sent) == 1
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$900"))
    watcher.check_favorite(fresh(fav))
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$450"))
    watcher.check_favorite(fresh(fav))
    assert len(sent) == 2


def test_favorite_above_target_does_not_fire(monkeypatch, fav, sent):
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$900"))
    assert watcher.check_favorite(fresh(fav))["notified"] is False
    assert sent == []


def test_favorite_error_recorded_no_notify(monkeypatch, fav, sent):
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$450", status=503))
    assert watcher.check_favorite(fresh(fav))["ok"] is False
    updated = fresh(fav)
    assert "503" in updated["last_error"] and updated["last_price_twd"] is None
    assert sent == []


def test_changing_target_resets_notification_state(monkeypatch, fav, sent):
    db.save_settings(fav["user_id"], {"telegram_chat_id": "1", "telegram_token": "t"})
    monkeypatch.setattr(watcher, "safe_get", lambda *a, **k: page("NT$450"))
    watcher.check_favorite(fresh(fav))
    db.set_favorite_target(fav["id"], fav["user_id"], 460)
    watcher.check_favorite(fresh(fav))
    assert len(sent) == 2


def test_due_scan_respects_recheck_interval(monkeypatch, fav):
    calls = []
    monkeypatch.setattr(watcher, "check_favorite", lambda f: calls.append(f["id"]))
    assert watcher.check_due_favorites(pause_seconds=0) == 1
    db.set_favorite_check(fav["id"], price_twd=900)
    assert watcher.check_due_favorites(pause_seconds=0) == 0
    assert len(calls) == 1


def test_due_scan_enforces_per_user_cap(monkeypatch, make_user):
    import quota
    u = make_user()
    for i in range(quota.FREE_CAPS.favorite_targets + 5):
        f = db.add_favorite(u.id, {"url": f"https://s.example.com/{i}"})
        db.set_favorite_target(f["id"], u.id, 100)
    calls = []
    monkeypatch.setattr(watcher, "check_favorite", lambda f: calls.append(f["id"]))
    assert watcher.check_due_favorites(pause_seconds=0) == quota.FREE_CAPS.favorite_targets


def test_due_scan_survives_single_failure(monkeypatch, make_user):
    u = make_user()
    for i in range(2):
        f = db.add_favorite(u.id, {"url": f"https://s.example.com/{i}"})
        db.set_favorite_target(f["id"], u.id, 100)

    def boom(f):
        raise RuntimeError("壞掉")

    monkeypatch.setattr(watcher, "check_favorite", boom)
    assert watcher.check_due_favorites(pause_seconds=0) == 2


# ---------- 刪除路徑(外鍵已開啟,等同 Postgres 行為)----------

def _seed_everything(uid, other_id):
    """每張有外鍵指向 tr_users / tr_posts 的表都放資料,連別人的文章/討論串上的互動也放。"""
    with db.SessionLocal() as s:
        own_post = db.Post(slug="own", title="t", author_id=uid)
        other_post = db.Post(slug="other", title="t", author_id=other_id)
        own_thread = db.Thread(category="tech", title="t", author_id=uid)
        other_thread = db.Thread(category="tech", title="t", author_id=other_id, reply_count=1)
        run = db.Run(id="run1", user_id=uid, keywords=["k"])
        s.add_all([own_post, other_post, own_thread, other_thread, run])
        s.flush()
        c1 = db.PostComment(post_id=own_post.id, author_id=other_id, content="別人留在我文章")
        c2 = db.PostComment(post_id=other_post.id, author_id=uid, content="我留在別人文章")
        s.add_all([c1, c2])
        s.flush()
        s.add_all([
            db.PostCommentLike(comment_id=c1.id, user_id=other_id),
            db.PostCommentLike(comment_id=c1.id, user_id=uid),
            db.PostCommentLike(comment_id=c2.id, user_id=other_id),
            db.PostLike(post_id=own_post.id, user_id=other_id),
            db.PostLike(post_id=other_post.id, user_id=uid),
            db.PostReaction(post_id=own_post.id, user_id=other_id, emoji="A"),
            db.PostReaction(post_id=other_post.id, user_id=uid, emoji="B"),
            db.Reply(thread_id=own_thread.id, author_id=other_id, content="r"),
            db.Reply(thread_id=other_thread.id, author_id=uid, content="r"),
            db.Settings(user_id=uid), db.Schedule(user_id=uid), db.Watch(user_id=uid, url="https://x.example.com"),
            db.Favorite(user_id=uid, url="https://x.example.com"),
            db.Report(reporter_id=uid), db.Subscription(subscriber_id=uid, author_id=other_id),
            db.Subscription(subscriber_id=other_id, author_id=uid),
            db.AiChatLog(user_id=uid), db.BindCode(code="ABC123", user_id=uid),
            db.PushSub(user_id=uid, endpoint="https://push.example.com/1"), db.Notification(user_id=uid),
            db.AiCost(user_id=uid), db.Usage(user_id=uid, day="2026-01-01"),
            db.CrawlItem(run_id="run1", payload={"title": "x"}),
            db.Job(id="job1", user_id=uid, kind="crawl"),
            db.PriceObservation(user_id=uid, url="https://x.example.com", url_hash="h", price_twd=1),
        ])
        s.commit()
        return own_post.id, other_post.id, own_thread.id, other_thread.id


def _user_fk_columns():
    for table in db.Base.metadata.sorted_tables:
        for col in table.columns:
            if any(fk.target_fullname == "tr_users.id" for fk in col.foreign_keys):
                yield table, col


def test_foreign_keys_are_actually_enforced():
    with db.SessionLocal() as s:
        s.add(db.Favorite(user_id=987654, url="https://x.example.com"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_no_ddl_on_postgres_startup(monkeypatch):
    """Postgres 的結構由 migrate.py 管理:init_db 在非 SQLite 上不能碰 schema。"""
    monkeypatch.setattr(db, "IS_SQLITE", False)
    monkeypatch.setattr(db.Base.metadata, "create_all", lambda *a, **k: pytest.fail("冷啟動不可跑 DDL"))
    db.init_db()


def test_seed_covers_every_user_fk_table(make_user):
    u, v = make_user(), make_user()
    _seed_everything(u.id, v.id)
    with db.engine.connect() as conn:
        for table, col in _user_fk_columns():
            rows = conn.execute(table.select().where(col == u.id)).fetchall()
            assert rows, f"測試資料沒涵蓋 {table.name}.{col.name}"


def test_delete_user_removes_all_dependents(make_user):
    u, v = make_user(), make_user()
    _, other_post, _, other_thread = _seed_everything(u.id, v.id)
    assert db.delete_user(u.id) is True
    with db.engine.connect() as conn:
        for table, col in _user_fk_columns():
            assert conn.execute(table.select().where(col == u.id)).fetchall() == [], f"{table.name} 還有殘留"
    with db.SessionLocal() as s:
        assert s.get(db.User, u.id) is None
        assert s.get(db.User, v.id) is not None
        assert s.get(db.Post, other_post) is not None
        t = s.get(db.Thread, other_thread)
        assert t is not None and t.reply_count == 0
        assert s.query(db.CrawlItem).count() == 0


def test_delete_user_api(client, make_user, bearer):
    u, v = make_user(), make_user()
    _seed_everything(u.id, v.id)
    assert client.delete("/api/auth/me", headers=bearer(u)).status_code == 200


def test_delete_missing_user():
    assert db.delete_user(99999) is False


def test_delete_post_removes_all_dependents(make_user):
    u, v = make_user(), make_user()
    own_post, other_post, _, _ = _seed_everything(u.id, v.id)
    assert db.delete_post(own_post) is True
    with db.SessionLocal() as s:
        assert s.get(db.Post, own_post) is None
        for model in (db.PostComment, db.PostLike, db.PostReaction):
            assert s.query(model).filter_by(post_id=own_post).count() == 0
        assert s.query(db.PostLike).filter_by(post_id=other_post).count() == 1
        assert s.query(db.PostCommentLike).count() == 1  # 只剩別人文章上的留言讚


def test_delete_post_api_with_comments(client, make_user, bearer):
    u, v = make_user(), make_user()
    own_post, *_ = _seed_everything(u.id, v.id)
    assert client.delete(f"/api/blog/{own_post}", headers=bearer(u)).status_code == 200


def test_admin_delete_comment_with_likes(make_user):
    u, v = make_user(), make_user()
    _seed_everything(u.id, v.id)
    with db.SessionLocal() as s:
        cid = s.query(db.PostComment).first().id
    assert db.set_comment_status(cid, "delete") is True


# ---------- 資料遺失 ----------

def test_failed_job_still_saved(make_user, monkeypatch):
    import worker
    u = make_user()

    def boom(config, **kw):
        raise RuntimeError("爬蟲炸了")

    monkeypatch.setattr(worker, "run_crawl", boom)
    job = manager.create(CrawlConfig(keywords=["k"]), u.id)
    worker.run_job(job.id)
    assert manager.get(job.id).status == "error"
    saved = db.get_run(job.id, u.id)
    assert saved is not None and saved["status"] == "error" and saved["keywords"] == ["k"]


def test_listing_extras_do_not_drop_remaining_results(monkeypatch):
    results = [{"title": f"關鍵字 {i}", "url": f"https://s{i}.example.com/p{i}", "snippet": "關鍵字"} for i in range(5)]

    def fake_detail(driver, item, min_sleep, max_sleep):
        return {**item, "category": "", "price": "",
                "_extra_products": [{"title": "額外A", "url": "https://x.example.com/a"}, {"title": "額外B", "url": "https://x.example.com/b"}]}

    monkeypatch.setattr(runner, "build_driver", lambda headless: SimpleNamespace(quit=lambda: None))
    monkeypatch.setattr(runner, "search_api", lambda prov, kw, pages: results)
    monkeypatch.setattr(runner, "resolve_order", lambda p: ["duckduckgo"])
    monkeypatch.setattr(runner, "scrape_detail_page", fake_detail)
    monkeypatch.delenv("DISABLE_BROWSER", raising=False)

    cfg = CrawlConfig(keywords=["關鍵字"], search_provider="duckduckgo", scrape_details=True, max_detail_pages=2,
                      min_sleep=0.5, max_sleep=0.5)
    urls = {r["url"] for r in runner.run_crawl(cfg)["records"]}
    assert {f"https://s{i}.example.com/p{i}" for i in range(5)} <= urls
    assert {"https://x.example.com/a", "https://x.example.com/b"} <= urls


# ---------- 廣播 ----------

@pytest.fixture
def mail(monkeypatch):
    import mailer
    sent = []
    monkeypatch.setattr(mailer, "mail_available", lambda: True)
    monkeypatch.setattr(mailer, "send_email", lambda to, subject, html: sent.append(to) or (True, "ok"))
    return sent


def test_emails_by_segment(make_user):
    make_user("plain@example.com")
    make_user("vip@example.com", privileged=True)
    make_user("banned@example.com", privileged=True, banned=True)
    assert db.emails_by_segment("privileged") == ["vip@example.com"]
    assert set(db.emails_by_segment("all")) == {"plain@example.com", "vip@example.com"}


def test_admin_broadcast_email_respects_segment(client, make_user, bearer, mail):
    admin = make_user("admin@example.com", email_verified=True)
    make_user("plain@example.com")
    make_user("vip@example.com", privileged=True)
    r = client.post("/api/admin/broadcast", json={"title": "t", "channels": ["email"], "segment": "privileged"}, headers=bearer(admin))
    assert r.status_code == 200 and mail == ["vip@example.com"]


def _due_broadcast(segment="all", channels=None):
    return db.schedule_broadcast("t", "b", "", channels or ["email"], segment, datetime.now(timezone.utc) - timedelta(minutes=1))


def test_scheduled_broadcast_respects_segment(make_user, mail):
    make_user("plain@example.com")
    make_user("vip@example.com", privileged=True)
    _due_broadcast("privileged")
    assert db.run_due_broadcasts() == 1
    assert mail == ["vip@example.com"]


def test_scheduled_broadcast_not_resent(make_user, mail):
    make_user("a@example.com")
    bid = _due_broadcast()
    assert db.run_due_broadcasts() == 1
    assert db.run_due_broadcasts() == 0
    assert mail == ["a@example.com"]
    item = next(i for i in db.list_scheduled_broadcasts() if i["id"] == bid)
    assert item["sent"] is True and item["result"].get("email") == 1


def test_overlapping_runs_only_send_once(make_user, monkeypatch, mail):
    make_user("a@example.com")
    _due_broadcast()
    real = db.broadcast
    inner = []

    def overlapping(*a, **k):
        # 第一輪正在送的時候,第二輪排程剛好也觸發
        inner.append(db.run_due_broadcasts())
        return real(*a, **k)

    monkeypatch.setattr(db, "broadcast", overlapping)
    assert db.run_due_broadcasts() == 1
    assert inner == [0]
    assert mail == ["a@example.com"]


def test_failed_broadcast_recorded_and_stays_claimed(make_user, monkeypatch):
    make_user("a@example.com")
    bid = _due_broadcast(channels=["inapp"])

    def boom(*a, **k):
        raise RuntimeError("壞掉")

    monkeypatch.setattr(db, "broadcast", boom)
    db.run_due_broadcasts()
    item = next(i for i in db.list_scheduled_broadcasts() if i["id"] == bid)
    assert item["sent"] is True and "壞掉" in item["result"]["error"]
