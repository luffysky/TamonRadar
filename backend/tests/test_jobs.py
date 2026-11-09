"""持久化工作、工作者、派發器、限流、R2 直傳:全部不靠行程記憶體。"""
import sys
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest

import app as app_module
import bots
import db
import internal_routes  # noqa: F401
import jobs
import quota
import ratelimit
import scheduler
import uploader
import watcher
import worker
from crawler import robots, runner, site_crawler
from crawler.config import BudgetExhausted, CrawlConfig
from jobs import TooManyJobs, manager

CRON = {"Authorization": "Bearer test-cron-secret"}


def far() -> float:
    return time.monotonic() + 60


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def fake_search(monkeypatch):
    calls = []

    def _search(prov, kw, pages):
        calls.append(kw)
        return [{"title": f"{kw} 商品", "url": f"https://s.example.com/{kw}", "snippet": kw, "keyword": kw, "domain": "s.example.com"}]

    monkeypatch.setattr(runner, "search_api", _search)
    monkeypatch.setattr(runner, "resolve_order", lambda p: ["duckduckgo"])
    monkeypatch.setattr(runner, "light_enrich", lambda *a, **k: 0)
    return calls


def _cfg(*kws, **kw):
    return CrawlConfig(keywords=list(kws) or ["a"], search_provider="duckduckgo", scrape_details=False, **kw)


def _job(jid):
    with db.SessionLocal() as s:
        return s.get(db.Job, jid)


# ---------- 建立與認領 ----------

def test_create_queues_and_returns_immediately(user, fake_search):
    j = manager.create(_cfg(), user.id)
    assert j.status == "queued" and fake_search == []
    assert jobs.events_since(j.id)[0]["type"] == "queued"


def test_per_user_limit_at_creation(user):
    manager.create(_cfg(), user.id, max_active=1)
    with pytest.raises(TooManyJobs):
        manager.create(_cfg(), user.id, max_active=1)


def test_claim_enforces_per_user_concurrency(user):
    a = manager.create(_cfg(), user.id)
    b = manager.create(_cfg(), user.id)
    first = jobs.claim_next("w1", far())
    assert first.id == a.id
    assert jobs.claim_next("w2", far()) is None  # 免費使用者同時只能跑 1 個
    first.finish("done")
    assert jobs.claim_next("w2", far()).id == b.id


def test_claim_enforces_global_limit(make_user, monkeypatch):
    monkeypatch.setattr(jobs, "MAX_CONCURRENT", 1)
    manager.create(_cfg(), make_user().id)
    manager.create(_cfg(), make_user().id)
    assert jobs.claim_next("w1", far()) is not None
    assert jobs.claim_next("w2", far()) is None


def test_bot_priority_ahead_of_crawl(user):
    manager.create(_cfg(), user.id)
    bot = jobs.enqueue("bot_telegram", config={"chat_id": 1, "text": "hi"}, priority=10, max_attempts=1)
    assert jobs.claim_next("w", far()).id == bot


# ---------- 完整流程 ----------

def test_worker_runs_job_and_saves_run(user, fake_search, client, bearer):
    j = manager.create(_cfg("a", "b"), user.id)
    assert worker.run(budget=30)["processed"] == 1
    assert manager.get(j.id).status == "done" and fake_search == ["a", "b"]
    assert db.get_run(j.id, user.id)["status"] == "done"
    body = client.get(f"/api/crawl/{j.id}/events", headers=bearer(user)).json()
    assert body["finished"] is True and body["status"] == "done"
    assert len(body["result"]["records"]) == 2 and any(e["type"] == "done" for e in body["events"])


def test_events_polled_incrementally(user, fake_search, client, bearer):
    j = manager.create(_cfg("a"), user.id)
    h = bearer(user)
    first = client.get(f"/api/crawl/{j.id}/events", headers=h).json()
    assert first["finished"] is False and first["status"] == "queued"
    worker.run(budget=30)
    second = client.get(f"/api/crawl/{j.id}/events", headers=h, params={"after": first["last_seq"]}).json()
    assert [e["seq"] for e in second["events"]] == list(range(first["last_seq"] + 1, second["last_seq"] + 1))
    assert second["finished"] is True


def test_budget_stop_then_resume_without_repeating(user, fake_search, monkeypatch):
    j = manager.create(_cfg("a", "b", "c"), user.id)
    budget = {"left": 2}

    def fake_left(self):
        budget["left"] -= 1
        return budget["left"] >= 0

    monkeypatch.setattr(jobs.JobHandle, "budget_left", fake_left)
    h = jobs.claim_next("w1", far())
    worker.execute(h)
    row = _job(j.id)
    assert row.status == "queued" and row.cursor["next_keyword"] == 2 and row.attempts == 0
    assert fake_search == ["a", "b"]

    monkeypatch.setattr(jobs.JobHandle, "budget_left", lambda self: True)
    worker.execute(jobs.claim_next("w2", far()))
    assert manager.get(j.id).status == "done" and fake_search == ["a", "b", "c"]
    assert len(db.get_run(j.id, user.id)["records"]) == 3


def test_stop_request_honored_by_worker(user, fake_search, monkeypatch):
    j = manager.create(_cfg("a", "b"), user.id)
    h = jobs.claim_next("w", far())
    assert manager.stop(j.id) == "stopping"
    h._last_beat = 0   # 模擬已到心跳間隔
    worker.execute(h)
    assert manager.get(j.id).status == "stopped"
    assert db.get_run(j.id, user.id)["status"] == "stopped"


def test_stop_queued_finishes_immediately(user):
    j = manager.create(_cfg(), user.id)
    assert manager.stop(j.id) == "stopped"
    assert jobs.claim_next("w", far()) is None
    assert db.get_run(j.id, user.id)["status"] == "stopped"


def test_failed_worker_reclaimed_and_resumes(user, fake_search, monkeypatch):
    j = manager.create(_cfg("a", "b"), user.id)
    jobs.claim_next("dead", far()).checkpoint({"next_keyword": 1, "results": [], "api_dead": []})
    with db.SessionLocal() as s:
        s.get(db.Job, j.id).heartbeat_at = db._now() - timedelta(seconds=jobs.STALE_AFTER + 5)
        s.commit()
    h = jobs.claim_next("live", far())
    assert h is not None and h.id == j.id and h.cursor["next_keyword"] == 1
    assert _job(j.id).attempts == 1
    worker.execute(h)
    assert fake_search == ["b"] and manager.get(j.id).status == "done"


def test_gives_up_after_max_attempts(user):
    j = manager.create(_cfg(), user.id)
    for _ in range(3):
        jobs.claim_next("dead", far())
        with db.SessionLocal() as s:
            s.get(db.Job, j.id).heartbeat_at = db._now() - timedelta(seconds=jobs.STALE_AFTER + 5)
            s.commit()
    assert jobs.claim_next("next", far()) is None
    row = _job(j.id)
    assert row.status == "error" and row.attempts == 3
    assert db.get_run(j.id, user.id)["status"] == "error"


def test_zombie_worker_is_fenced(user):
    j = manager.create(_cfg(), user.id)
    old = jobs.claim_next("old", far())
    with db.SessionLocal() as s:
        s.get(db.Job, j.id).heartbeat_at = db._now() - timedelta(seconds=jobs.STALE_AFTER + 5)
        s.commit()
    new = jobs.claim_next("new", far())
    with pytest.raises(jobs.LostClaim):
        old.checkpoint({"x": 1})
    with pytest.raises(jobs.LostClaim):
        old.finish("done")
    new.finish("done")
    assert _job(j.id).status == "done"


# ---------- 整站爬 frontier ----------

def _page(links=(), items=()):
    hrefs = "".join(f'<a href="{u}">x</a>' for u in links)
    return SimpleNamespace(status_code=200, headers={"content-type": "text/html"}, text=f"<html><body>{hrefs}</body></html>")


@pytest.fixture
def site(monkeypatch):
    pages = {"https://s.example.com/": ["/a", "/b"], "https://s.example.com/a": ["/b", "/c"],
             "https://s.example.com/b": [], "https://s.example.com/c": []}
    fetched = []

    def _get(url, **k):
        fetched.append(url)
        return _page(pages.get(url, []))

    monkeypatch.setattr(site_crawler, "safe_get", _get)
    monkeypatch.setattr(site_crawler, "items_from_soup", lambda soup, url: [
        {"title": "共用項目", "url": "https://s.example.com/shared"}, {"title": f"項目 {url}", "url": url, "price": "NT$1"}])
    monkeypatch.setattr(site_crawler.time, "sleep", lambda s: None)
    monkeypatch.setattr(robots, "allowed", lambda u: True)
    monkeypatch.setattr(robots, "blocked", lambda u: False)
    return fetched


def _site_cfg(**kw):
    return CrawlConfig(keywords=["https://s.example.com/"], site_url="https://s.example.com/", site_max_pages=10, site_max_depth=3, **kw)


def test_site_crawl_resumes_from_db_frontier(user, site, monkeypatch):
    j = manager.create(_site_cfg(), user.id)
    budget = {"left": 2}

    def fake_left(self):
        budget["left"] -= 1
        return budget["left"] >= 0

    monkeypatch.setattr(jobs.JobHandle, "budget_left", fake_left)
    worker.execute(jobs.claim_next("w1", far()))
    assert _job(j.id).status == "queued" and len(site) == 2

    monkeypatch.setattr(jobs.JobHandle, "budget_left", lambda self: True)
    worker.execute(jobs.claim_next("w2", far()))
    assert manager.get(j.id).status == "done"
    assert len(site) == len(set(site)) == 4  # 沒有重抓
    run = db.get_run(j.id, user.id)
    assert run["summary"]["total"] == 5 and db.count_crawl_items(j.id) == 5  # 跨頁重複的項目只收一次
    with db.SessionLocal() as s:
        assert s.query(db.CrawlFrontier).filter_by(job_id=j.id).count() == 0


def test_site_crawl_crash_mid_page_is_idempotent(user, site):
    j = manager.create(_site_cfg(), user.id)
    h = jobs.claim_next("w", far())
    store = jobs.DbSiteStore(h)
    store.seed("https://s.example.com/")
    items = [{"title": "T", "url": "u", "category": "c", "domain": "d", "price": ""}]
    assert store.commit_page("https://s.example.com/", items, [("https://s.example.com/a", 1)]) == 1
    store2 = jobs.DbSiteStore(h)
    assert store2.commit_page("https://s.example.com/", items, []) == 0  # 重送同一頁不重複
    assert store2.total == 1


# ---------- 派發器 ----------

def _due(model, row_id, minutes=1):
    with db.SessionLocal() as s:
        s.get(model, row_id).next_run_at = db._now() - timedelta(minutes=minutes)
        s.commit()


def _jobs_of(kind):
    with db.SessionLocal() as s:
        return s.query(db.Job).filter_by(kind=kind).all()


def test_dispatch_fires_schedule_once_and_advances(user):
    sc = db.create_schedule(user.id, {"keywords": ["k"], "interval_hours": 24})
    assert scheduler.dispatch()["schedules"] == 1
    assert scheduler.dispatch()["schedules"] == 0
    assert len(_jobs_of("schedule")) == 1
    with db.SessionLocal() as s:
        row = s.get(db.Schedule, sc["id"])
    assert scheduler._aware(row.next_run_at) > db._now() + timedelta(hours=23)


def test_dispatch_skips_while_previous_job_active(user):
    sc = db.create_schedule(user.id, {"keywords": ["k"], "interval_hours": 24})
    scheduler.dispatch()
    _due(db.Schedule, sc["id"])
    assert scheduler.dispatch()["schedules"] == 0


def test_dispatch_after_job_finished_fires_again(user, monkeypatch):
    monkeypatch.setattr(scheduler, "run_crawl", lambda c, **k: {"records": [], "summary": {}})
    sc = db.create_schedule(user.id, {"keywords": ["k"], "interval_hours": 24, "provider": "duckduckgo"})
    scheduler.dispatch()
    worker.run(budget=30)
    assert db.list_notifications(user.id)["items"][0]["title"].startswith("📡 排程更新")
    with db.SessionLocal() as s:
        assert s.get(db.Schedule, sc["id"]).claim_job_id is None
    _due(db.Schedule, sc["id"])
    assert scheduler.dispatch()["schedules"] == 1


def test_loaded_data_without_next_run_not_all_fired(user):
    sc = db.create_schedule(user.id, {"keywords": ["k"], "interval_hours": 24})
    with db.SessionLocal() as s:
        row = s.get(db.Schedule, sc["id"])
        row.next_run_at = None
        row.last_run = db._now() - timedelta(hours=1)
        s.commit()
    assert scheduler.dispatch()["schedules"] == 0
    with db.SessionLocal() as s:
        assert scheduler._aware(s.get(db.Schedule, sc["id"]).next_run_at) > db._now()


def test_dispatch_watch_runs_check(user, monkeypatch):
    w = db.create_watch(user.id, {"url": "https://s.example.com/", "interval_minutes": 5})
    seen = []
    monkeypatch.setattr(watcher, "check_watch", lambda wid: seen.append(wid) or {"ok": True})
    assert scheduler.dispatch()["watches"] == 1
    worker.run(budget=30)
    assert seen == [w["id"]]


def test_interval_enforces_plan_minimum(user):
    w = db.create_watch(user.id, {"url": "https://s.example.com/", "interval_minutes": 1})
    scheduler.dispatch()
    with db.SessionLocal() as s:
        assert scheduler._aware(s.get(db.Watch, w["id"]).next_run_at) > db._now() + timedelta(minutes=4)


def test_broadcast_dispatched_once(user, monkeypatch):
    bid = db.schedule_broadcast("t", "b", "", ["inapp"], "all", db._now() - timedelta(minutes=1))
    assert scheduler.dispatch()["broadcasts"] == 1
    assert scheduler.dispatch()["broadcasts"] == 0
    worker.run(budget=30)
    assert db.list_notifications(user.id)["items"][0]["title"] == "t"
    with db.SessionLocal() as s:
        assert s.get(db.ScheduledBroadcast, bid).result["recipients"] == 1


def test_digest_only_once_per_day_and_not_on_first_boot(user):
    scheduler.dispatch()
    assert _jobs_of("digest") == []
    with db.SessionLocal() as s:
        s.get(db.CronState, "daily_digest").next_run_at = db._now() - timedelta(minutes=1)
        s.commit()
    scheduler.dispatch()
    scheduler.dispatch()
    assert len(_jobs_of("digest")) == 1


def test_digest_resumes_after_budget(make_user, monkeypatch):
    a, b = make_user(), make_user()
    db.save_settings(a.id, {"daily_digest": True})
    db.save_settings(b.id, {"daily_digest": True})
    jid = jobs.enqueue("digest")
    budget = {"left": 1}

    def fake_left(self):
        budget["left"] -= 1
        return budget["left"] >= 0

    monkeypatch.setattr(jobs.JobHandle, "budget_left", fake_left)
    worker.execute(jobs.claim_next("w1", far()))
    assert _job(jid).status == "queued"
    monkeypatch.setattr(jobs.JobHandle, "budget_left", lambda self: True)
    worker.execute(jobs.claim_next("w2", far()))
    for u in (a, b):
        assert len(db.list_notifications(u.id)["items"]) == 1


def test_schedule_notification_not_repeated_after_crash(user, monkeypatch):
    monkeypatch.setattr(scheduler, "run_crawl", lambda c, **k: pytest.fail("已存檔就不該重爬"))
    sent = []
    monkeypatch.setattr(scheduler.notify, "has_channel", lambda st: True)
    monkeypatch.setattr(scheduler.notify, "notify_all", lambda st, text, embed=None: sent.append(text) or {})
    sc = db.create_schedule(user.id, {"keywords": ["k"]})
    jid = jobs.enqueue("schedule", user_id=user.id, config={"schedule_id": sc["id"]})
    with db.SessionLocal() as s:
        s.get(db.Job, jid).cursor = {"charged": True, "saved": True, "message": "m", "notified": True}
        s.commit()
    worker.execute(jobs.claim_next("w", far()))
    assert sent == [] and _job(jid).status == "done"


# ---------- 內部端點 ----------

@pytest.mark.parametrize("path", ["/api/internal/worker", "/api/internal/dispatch"])
def test_internal_requires_secret(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get(path, headers=CRON).status_code == 200


def test_internal_fails_closed_without_secret(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "")
    assert client.get("/api/internal/worker", headers={"Authorization": "Bearer "}).status_code == 503


def test_trigger_noop_without_config(monkeypatch):
    monkeypatch.setattr(worker.requests, "post", lambda *a, **k: pytest.fail("不該送出"))
    assert worker.trigger() is False


def test_trigger_posts_when_configured(monkeypatch):
    calls = []
    monkeypatch.setenv("WORKER_TRIGGER_BASE", "https://api.example.com/")
    monkeypatch.setattr(worker.requests, "post", lambda url, **k: calls.append((url, k)) or SimpleNamespace())
    assert worker.trigger() is True
    assert calls[0][0] == "https://api.example.com/api/internal/worker"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-cron-secret"


def test_lost_trigger_only_delays(user, fake_search, client, bearer, monkeypatch):
    monkeypatch.setenv("WORKER_TRIGGER_BASE", "https://api.example.com")

    def boom(*a, **k):
        raise worker.requests.exceptions.ConnectionError("x")

    monkeypatch.setattr(worker.requests, "post", boom)
    r = client.post("/api/crawl", json={"keywords": ["a"], "search_provider": "duckduckgo", "scrape_details": False}, headers=bearer(user))
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert manager.get(jid).status == "queued"
    client.get("/api/internal/worker", headers=CRON)   # 下一次 cron
    assert manager.get(jid).status == "done"


# ---------- 機器人 ----------

def test_telegram_webhook_enqueues_and_acks(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3")
    monkeypatch.setattr(bots, "answer", lambda *a: pytest.fail("webhook 不該等 AI"))
    update = {"update_id": 77, "message": {"chat": {"id": 5}, "text": "你好", "from": {"username": "u"}}}
    assert client.post("/api/telegram/webhook/s3", json=update).status_code == 200
    assert client.post("/api/telegram/webhook/s3", json=update).status_code == 200  # Telegram 重送
    assert len(_jobs_of("bot_telegram")) == 1


def test_telegram_job_answers_and_scrubs_config(monkeypatch):
    sent = []
    monkeypatch.setattr(bots, "answer", lambda q, actor: "答案")
    monkeypatch.setattr(bots, "telegram_send", lambda chat, text: sent.append((chat, text)))
    jid = jobs.enqueue("bot_telegram", config={"chat_id": 5, "text": "問", "uname": "u"}, max_attempts=1)
    worker.run(budget=30)
    assert sent == [(5, "答案")]
    assert _job(jid).config == {}


def test_discord_defers_then_followup(client, monkeypatch):
    monkeypatch.setattr(bots, "verify_discord", lambda *a: True)
    monkeypatch.setattr(bots, "answer", lambda q, actor: "答")
    follow = []
    monkeypatch.setattr(bots, "_discord_followup", lambda app, tok, content: follow.append(content))
    body = {"id": "i1", "type": 2, "application_id": "app", "token": "tok", "data": {"name": "ask", "options": [{"name": "question", "value": "問"}]},
            "member": {"user": {"id": "9", "username": "n"}}}
    assert client.post("/api/discord/interactions", json=body).json() == {"type": 5}
    assert follow == []
    worker.run(budget=30)
    assert follow == ["答"]


# ---------- 上傳 / 匯出 ----------

@pytest.fixture
def r2_env(monkeypatch):
    for k, v in {"R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "AK", "R2_SECRET_ACCESS_KEY": "SK",
                 "R2_BUCKET_NAME": "bkt", "R2_URL": "https://cdn.example.com"}.items():
        monkeypatch.setenv(k, v)


def test_presign_signs_type_and_length(client, user, bearer, r2_env):
    r = client.post("/api/upload/presign", json={"filename": "a.png", "content_type": "image/png", "size": 123}, headers=bearer(user))
    assert r.status_code == 200
    data = r.json()
    assert data["url"].startswith("https://cdn.example.com/uploads/") and data["url"].endswith(".png")
    assert "content-length" in data["upload_url"].lower() and "content-type" in data["upload_url"].lower()
    assert "checksum" not in data["upload_url"].lower()  # R2 不接受 boto3 預設的 CRC 參數


def test_presign_rejects_over_50mb(client, user, bearer, r2_env):
    r = client.post("/api/upload/presign", json={"filename": "a", "size": 50 * 1024 * 1024 + 1}, headers=bearer(user))
    assert r.status_code == 413


def test_presign_requires_auth_and_r2(client, user, bearer):
    assert client.post("/api/upload/presign", json={"filename": "a", "size": 1}).status_code == 401
    assert client.post("/api/upload/presign", json={"filename": "a", "size": 1}, headers=bearer(user)).status_code == 503


def test_big_export_goes_to_signed_url(client, user, bearer, monkeypatch):
    monkeypatch.setattr(app_module, "_RESPONSE_LIMIT", 10)
    monkeypatch.setattr(uploader, "r2_available", lambda: True)
    monkeypatch.setattr(uploader, "store_export", lambda name, data, ctype: f"https://signed.example.com/{name}")
    db.create_run_record(user.id, "bigrun", ["k"], {"records": [{"title": "x" * 200, "url": "u"}], "summary": {}})
    r = client.get("/api/export/bigrun.csv", headers=bearer(user))
    assert r.status_code == 200 and r.json()["download_url"] == "https://signed.example.com/tammon_bigrun.csv"


def test_big_export_without_r2_is_explicit_error(client, user, bearer, monkeypatch):
    monkeypatch.setattr(app_module, "_RESPONSE_LIMIT", 10)
    db.create_run_record(user.id, "bigrun2", ["k"], {"records": [{"title": "x" * 200, "url": "u"}], "summary": {}})
    assert client.get("/api/export/bigrun2.csv", headers=bearer(user)).status_code == 413


def test_oversized_result_truncated_for_response(client, user, bearer, monkeypatch):
    monkeypatch.setattr(app_module, "_RESPONSE_LIMIT", 300)
    db.create_run_record(user.id, "r1", ["k"], {"records": [{"title": "x" * 80, "url": str(i)} for i in range(10)], "summary": {}})
    data = client.get("/api/history/r1", headers=bearer(user)).json()
    assert data["truncated"] is True and 0 < len(data["records"]) < 10 and data["total"] == 10


# ---------- 限流 / 無狀態 ----------

def test_rate_limit_is_shared_in_db():
    assert all(ratelimit.hit("k", 2, 60) for _ in range(2))
    assert ratelimit.hit("k", 2, 60) is False
    with db.SessionLocal() as s:
        assert s.get(db.RateLimitBucket, "k").hits == 2  # 超限的這次不計入


def test_rate_limit_window_expires(monkeypatch):
    assert ratelimit.hit("w", 1, 60)
    assert ratelimit.hit("w", 1, 60) is False
    real = time.time
    monkeypatch.setattr(ratelimit.time, "time", lambda: real() + 61)
    assert ratelimit.hit("w", 1, 60) is True


def test_rate_limit_falls_back_when_db_down(monkeypatch):
    monkeypatch.setattr(ratelimit, "_hit_db", lambda *a: (_ for _ in ()).throw(RuntimeError("db down")))
    assert ratelimit.hit("m", 1, 60) is True
    assert ratelimit.hit("m", 1, 60) is False


def test_selenium_not_imported_on_web_path():
    for name in ("selenium", "webdriver_manager", "apscheduler", "sse_starlette"):
        assert name not in sys.modules, name


def test_no_threads_started_on_job_create(user, monkeypatch):
    import threading
    monkeypatch.setattr(threading.Thread, "start", lambda self: pytest.fail("不該開執行緒"))
    manager.create(_cfg(), user.id)


# ---------- 清理與刪除 ----------

def test_maintenance_retention(user):
    j = manager.create(_cfg(), user.id)
    h = jobs.claim_next("w", far())
    h.finish("done")
    with db.SessionLocal() as s:
        row = s.get(db.Job, j.id)
        row.finished_at = db._now() - timedelta(days=60)
        s.query(db.JobEvent).filter_by(job_id=j.id).update({"created_at": db._now() - timedelta(days=60)})
        s.commit()
    ratelimit.hit("old", 1, 1)
    with db.SessionLocal() as s:
        s.get(db.RateLimitBucket, "old").expires_at = 1.0
        s.commit()
    jobs.enqueue("maintenance", max_attempts=1)
    worker.run(budget=30)
    assert manager.get(j.id) is None and jobs.events_since(j.id) == []
    with db.SessionLocal() as s:
        assert s.get(db.RateLimitBucket, "old") is None


def test_delete_user_with_jobs_and_events(user, site):
    db.save_settings(user.id, {"daily_digest": True})
    j = manager.create(_site_cfg(), user.id)
    h = jobs.claim_next("w", far())
    store = jobs.DbSiteStore(h)
    store.seed("https://s.example.com/")
    db.add_price_observation(user.id, "https://s.example.com/", 100, "watch", 1)
    assert db.delete_user(user.id) is True
    with db.SessionLocal() as s:
        assert s.get(db.Job, j.id) is None
        assert s.query(db.CrawlFrontier).filter_by(job_id=j.id).count() == 0
        assert s.query(db.PriceObservation).count() == 0


def test_price_history_includes_watch_observations(user):
    db.add_price_observation(user.id, "https://s.example.com/p", 321, "watch", 1)
    assert db.price_history(user.id, "https://s.example.com/p")[0]["price_twd"] == 321


# ---------- 狀態機 / 例外 ----------

def test_budget_exhausted_is_not_failure(user, monkeypatch):
    j = manager.create(_cfg(), user.id)

    def raises(config, **k):
        raise BudgetExhausted()

    monkeypatch.setattr(worker, "run_crawl", raises)
    worker.execute(jobs.claim_next("w", far()))
    assert _job(j.id).status == "queued" and _job(j.id).attempts == 0


def test_caps_helper_used(user):
    assert quota.caps_for(user).concurrent_jobs == 1


def test_stop_seen_even_when_checkpoints_are_frequent(user):
    """每次存斷點都會更新心跳時間;停止旗標必須在存斷點時一併讀到。"""
    j = manager.create(_cfg("a", "b"), user.id)
    h = jobs.claim_next("w", far())
    manager.stop(j.id)
    h.checkpoint({"next_keyword": 1})
    assert h.should_stop() is True
