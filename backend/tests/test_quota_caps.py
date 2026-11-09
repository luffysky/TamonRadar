"""AI 花費閘門、額度與爬蟲/排程/監看上限。"""
from types import SimpleNamespace

import pytest

import ai
import app as app_module
import bots
import db
import quota
import ratelimit
from crawler.config import CrawlConfig
from jobs import Job, TooManyJobs, manager


@pytest.fixture
def fake_llm(monkeypatch):
    """讓 ai_complete 走到「呼叫模型」前的所有檢查,但完全不連外。"""
    calls = []

    class Fake:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, model, max_tokens, messages):
            calls.append({"max_tokens": max_tokens, "prompt": messages[0]["content"]})
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="答案"))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

    import openai
    monkeypatch.setattr(openai, "OpenAI", Fake)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-not-real")
    return calls


# ---------- 匿名 ----------

def test_assistant_requires_login(client, fake_llm):
    assert client.post("/api/assistant", json={"question": "hi"}).status_code == 401
    assert fake_llm == []


def test_insights_ai_requires_login(client, fake_llm):
    assert client.post("/api/insights/ai", json={"records": []}).status_code == 401
    assert fake_llm == []


def test_ai_complete_refuses_without_identity(fake_llm):
    with pytest.raises(quota.QuotaExceeded):
        ai.ai_complete("hello")
    assert fake_llm == []


# ---------- 輸入上限 ----------

def test_assistant_question_capped(client, make_user, bearer, fake_llm):
    r = client.post("/api/assistant", json={"question": "x" * 2001}, headers=bearer(make_user()))
    assert r.status_code == 400 and fake_llm == []


def test_history_entries_truncated(client, make_user, bearer, fake_llm):
    history = [{"role": "user", "content": "H" * 50000}]
    client.post("/api/assistant", json={"question": "hi", "history": history}, headers=bearer(make_user()))
    assert fake_llm[0]["prompt"].count("H") <= 2100


def test_central_prompt_and_token_limits(make_user, fake_llm):
    ai.ai_complete("y" * (ai.MAX_PROMPT_CHARS + 500), max_tokens=999999, user_id=make_user().id)
    assert len(fake_llm[0]["prompt"]) == ai.MAX_PROMPT_CHARS
    assert fake_llm[0]["max_tokens"] == ai.MAX_OUTPUT_TOKENS


def test_summarize_records_capped(client, make_user, bearer):
    r = client.post("/api/summarize", json={"records": [{"title": "x"}] * 2001}, headers=bearer(make_user()))
    assert r.status_code == 400


# ---------- 集中額度 ----------

def test_blog_ai_now_metered(client, make_user, bearer, fake_llm, monkeypatch):
    monkeypatch.setenv("FREE_AI_DAILY", "2")
    user = make_user()
    h = bearer(user)
    assert client.post("/api/blog/ai-write", json={"topic": "a"}, headers=h).status_code == 200
    assert client.post("/api/blog/ai-write", json={"topic": "b"}, headers=h).status_code == 200
    assert client.post("/api/blog/ai-write", json={"topic": "c"}, headers=h).status_code == 429
    assert db.quota_today(user.id)["ai"] == 2 and len(fake_llm) == 2


def test_endpoint_charges_exactly_once(client, make_user, bearer, fake_llm):
    user = make_user()
    db.create_run_record(user.id, "r1", ["k"], {"records": [{"title": "A", "url": "u"}], "summary": {}})
    assert client.post("/api/ai/chat", json={"run_id": "r1", "question": "q"}, headers=bearer(user)).status_code == 200
    assert db.quota_today(user.id)["ai"] == 1


def test_no_provider_does_not_charge(client, make_user, bearer):
    user = make_user()
    client.post("/api/blog/ai-write", json={"topic": "a"}, headers=bearer(user))
    assert db.quota_today(user.id)["ai"] == 0


def test_ai_per_minute_limit_for_free_users(make_user, fake_llm):
    user = make_user()
    for _ in range(quota.AI_PER_MINUTE):
        ai.ai_complete("hi", user_id=user.id)
    with pytest.raises(ratelimit.RateLimited):
        ai.ai_complete("hi", user_id=user.id)
    assert db.quota_today(user.id)["ai"] == quota.AI_PER_MINUTE


# ---------- 付費 / 特權不變 ----------

@pytest.mark.parametrize("kw", [{"plan": "pro"}, {"privileged": True}])
def test_paid_and_privileged_unlimited(make_user, fake_llm, monkeypatch, kw):
    monkeypatch.setenv("FREE_AI_DAILY", "1")
    user = make_user(**kw)
    for _ in range(quota.AI_PER_MINUTE + 3):
        ai.ai_complete("hi", user_id=user.id)
    assert db.quota_today(user.id)["ai"] == 0


def test_verified_admin_unlimited(make_user, fake_llm, monkeypatch):
    monkeypatch.setenv("FREE_AI_DAILY", "1")
    user = make_user("admin@example.com", email_verified=True)
    ai.ai_complete("a", user_id=user.id)
    ai.ai_complete("b", user_id=user.id)
    assert db.quota_today(user.id)["ai"] == 0


def test_admin_set_pro_flow_unchanged(client, make_user, bearer):
    admin = make_user("admin@example.com", email_verified=True)
    user = make_user()
    assert client.get("/api/quota", headers=bearer(user)).json()["unlimited"] is False
    assert client.post(f"/api/admin/users/{user.id}/plan", json={"plan": "pro"}, headers=bearer(admin)).status_code == 200
    assert client.get("/api/quota", headers=bearer(user)).json()["unlimited"] is True
    assert client.post(f"/api/admin/users/{user.id}/plan", json={"plan": "gold"}, headers=bearer(admin)).status_code == 400


def test_free_quota_message_and_status(make_user, monkeypatch):
    monkeypatch.setenv("FREE_SEARCH_DAILY", "1")
    user = make_user()
    quota.enforce(user, "search")
    with pytest.raises(quota.QuotaExceeded) as e:
        quota.enforce(user, "search")
    assert "每日 1 次" in e.value.message


# ---------- 機器人 ----------

def test_bot_limited_per_actor(fake_llm, monkeypatch):
    monkeypatch.setattr(quota, "BOT_AI_PER_HOUR", 2)
    assert bots.answer("q1", "telegram:1") == "答案"
    assert bots.answer("q2", "telegram:1") == "答案"
    assert "稍後" in bots.answer("q3", "telegram:1")
    assert bots.answer("q4", "telegram:2") == "答案"
    assert len(fake_llm) == 3


def test_bot_global_cap(fake_llm, monkeypatch):
    monkeypatch.setattr(quota, "BOT_AI_DAILY", 1)
    assert bots.answer("q1", "telegram:1") == "答案"
    assert "額度" in bots.answer("q2", "telegram:2")


def test_bot_cost_recorded_without_user(fake_llm):
    bots.answer("q1", "telegram:42")
    with db.SessionLocal() as s:
        row = s.query(db.AiCost).one()
    assert row.user_id is None and row.actor == "telegram:42" and row.in_tokens == 10


def test_admin_costs_include_bot_calls(fake_llm):
    bots.answer("q1", "telegram:42")
    assert db.admin_ai_costs()["recent"][0]["email"] == "telegram:42"


def test_user_cost_recorded(make_user, fake_llm):
    user = make_user()
    ai.ai_complete("q", user_id=user.id)
    with db.SessionLocal() as s:
        assert s.query(db.AiCost).one().user_id == user.id


# ---------- 圖片 ----------

@pytest.fixture
def fake_image(monkeypatch):
    calls = []

    class Fake:
        def __init__(self, **kw):
            self.images = SimpleNamespace(generate=self._gen)

        def _gen(self, **kw):
            calls.append(kw)
            return SimpleNamespace(data=[SimpleNamespace(b64_json="aGVsbG8=", url=None)])

    import openai
    monkeypatch.setattr(openai, "OpenAI", Fake)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-not-real")
    return calls


def test_image_requires_identity(fake_image):
    with pytest.raises(quota.QuotaExceeded):
        ai.generate_image("p")
    assert fake_image == []


def test_image_daily_cap_for_free(make_user, fake_image):
    user = make_user()
    for _ in range(quota.FREE_IMAGE_DAILY):
        assert ai.generate_image("p", user_id=user.id) == b"hello"
    with pytest.raises(ratelimit.RateLimited):
        ai.generate_image("p", user_id=user.id)
    assert len(fake_image) == quota.FREE_IMAGE_DAILY
    assert db.quota_today(user.id)["ai"] == quota.FREE_IMAGE_DAILY


def test_cover_endpoint_passes_user_to_gate(client, make_user, bearer, fake_image, monkeypatch):
    import uploader
    monkeypatch.setattr(uploader, "r2_available", lambda: True)
    monkeypatch.setattr(uploader, "upload", lambda *a, **k: "https://cdn.example.com/c.png")
    user = make_user()
    assert client.post("/api/blog/ai-cover", json={"title": "t"}, headers=bearer(user)).status_code == 200
    assert db.quota_today(user.id)["ai"] == 1


# ---------- 爬蟲上限 ----------

@pytest.fixture
def captured_jobs(monkeypatch):
    created = []

    def fake_create(config, user_id, max_active=None):
        job = SimpleNamespace(id=f"j{len(created)}", status="pending", config=config, max_active=max_active)
        created.append(job)
        return job

    monkeypatch.setattr(app_module.manager, "create", fake_create)
    return created


def test_free_keyword_cap(client, make_user, bearer, captured_jobs):
    user = make_user()
    r = client.post("/api/crawl", json={"keywords": [f"k{i}" for i in range(7)]}, headers=bearer(user))
    assert r.status_code == 400 and captured_jobs == []
    assert db.quota_today(user.id)["search"] == 0


def test_free_pages_and_detail_clamped(client, make_user, bearer, captured_jobs):
    r = client.post("/api/crawl", json={"keywords": ["k"], "google_pages_per_keyword": 20, "max_detail_pages": 500},
                    headers=bearer(make_user()))
    assert r.status_code == 200
    cfg = captured_jobs[0].config
    assert cfg.google_pages_per_keyword == quota.FREE_CAPS.pages
    assert cfg.max_detail_pages == quota.FREE_CAPS.detail_pages
    assert captured_jobs[0].max_active == quota.FREE_CAPS.concurrent_jobs


def test_pro_gets_higher_caps(client, make_user, bearer, captured_jobs):
    r = client.post("/api/crawl", json={"keywords": [f"k{i}" for i in range(20)], "google_pages_per_keyword": 20},
                    headers=bearer(make_user(plan="pro")))
    assert r.status_code == 200 and captured_jobs[0].config.google_pages_per_keyword == 20


def test_keyword_length_capped(client, make_user, bearer, captured_jobs):
    assert client.post("/api/crawl", json={"keywords": ["x" * 201]}, headers=bearer(make_user())).status_code == 400


def test_site_crawl_pages_clamped(client, make_user, bearer, captured_jobs, public_dns):
    r = client.post("/api/crawl-site", json={"url": "https://shop.example.com/", "max_pages": 5000, "max_depth": 12},
                    headers=bearer(make_user()))
    assert r.status_code == 200
    assert captured_jobs[0].config.site_max_pages == quota.FREE_CAPS.site_pages
    assert captured_jobs[0].config.site_max_depth == quota.FREE_CAPS.site_depth


def test_site_crawl_pro_keeps_env_cap(client, make_user, bearer, captured_jobs, public_dns):
    client.post("/api/crawl-site", json={"url": "https://shop.example.com/", "max_pages": 5000}, headers=bearer(make_user(plan="pro")))
    assert captured_jobs[0].config.site_max_pages == 5000


def _running_job(user_id):
    job = Job(CrawlConfig(keywords=["k"]), user_id)
    job.status = "running"
    manager._jobs[job.id] = job
    return job


def test_concurrent_job_limit_blocks_and_does_not_charge(client, make_user, bearer):
    user = make_user()
    _running_job(user.id)
    r = client.post("/api/crawl", json={"keywords": ["k"]}, headers=bearer(user))
    assert r.status_code == 429
    assert db.quota_today(user.id)["search"] == 0


def test_manager_enforces_limit_atomically(make_user):
    user = make_user()
    _running_job(user.id)
    with pytest.raises(TooManyJobs):
        manager.create(CrawlConfig(keywords=["k"]), user.id, max_active=1)


def test_finished_job_frees_slot(make_user):
    user = make_user()
    _running_job(user.id).status = "done"
    assert manager.active_count(user.id) == 0


# ---------- 排程 / 監看上限 ----------

def test_schedule_count_limit(client, make_user, bearer):
    h = bearer(make_user())
    for i in range(quota.FREE_CAPS.schedules):
        assert client.post("/api/schedules", json={"keywords": [f"k{i}"]}, headers=h).status_code == 200
    assert client.post("/api/schedules", json={"keywords": ["x"]}, headers=h).status_code == 429


def test_schedule_interval_and_pages_clamped(client, make_user, bearer):
    r = client.post("/api/schedules", json={"keywords": ["k"], "interval_hours": 1, "pages": 20, "max_detail": 500},
                    headers=bearer(make_user()))
    data = r.json()
    assert data["interval_hours"] == quota.FREE_CAPS.min_schedule_hours
    assert data["pages"] == quota.FREE_CAPS.pages
    assert data["max_detail"] == quota.FREE_CAPS.detail_pages


def test_schedule_keyword_cap(client, make_user, bearer):
    r = client.post("/api/schedules", json={"keywords": [f"k{i}" for i in range(7)]}, headers=bearer(make_user()))
    assert r.status_code == 400


def test_existing_oversized_schedule_can_still_be_toggled(client, make_user, bearer):
    user = make_user()
    kws = [f"k{i}" for i in range(9)]
    sc = db.create_schedule(user.id, {"keywords": kws})
    r = client.patch(f"/api/schedules/{sc['id']}", json={"keywords": kws, "enabled": False}, headers=bearer(user))
    assert r.status_code == 200


def test_watch_count_limit(client, make_user, bearer, public_dns):
    h = bearer(make_user())
    for i in range(quota.FREE_CAPS.watches):
        assert client.post("/api/watches", json={"url": f"https://s.example.com/{i}"}, headers=h).status_code == 200
    assert client.post("/api/watches", json={"url": "https://s.example.com/x"}, headers=h).status_code == 429


def test_watch_interval_clamped(client, make_user, bearer, public_dns):
    r = client.post("/api/watches", json={"url": "https://s.example.com/", "interval_minutes": 1}, headers=bearer(make_user()))
    assert r.json()["interval_minutes"] == quota.FREE_CAPS.min_watch_minutes


def test_pro_watch_interval_keeps_minimum_one(client, make_user, bearer, public_dns):
    r = client.post("/api/watches", json={"url": "https://s.example.com/", "interval_minutes": 1}, headers=bearer(make_user(plan="pro")))
    assert r.json()["interval_minutes"] == 1


def test_scheduled_run_consumes_search_quota_and_skips_when_exhausted(make_user, monkeypatch):
    import scheduler
    monkeypatch.setenv("FREE_SEARCH_DAILY", "0")
    user = make_user()
    sc = db.create_schedule(user.id, {"keywords": ["k"], "enabled": True})
    monkeypatch.setattr(scheduler, "run_crawl", lambda c: pytest.fail("額度用完不該爬"))
    scheduler._run(sc["id"])
    assert db.list_notifications(user.id)["items"][0]["title"] == "📡 排程略過"


def test_favorite_target_cap(client, make_user, bearer):
    user = make_user()
    h = bearer(user)
    ids = [db.add_favorite(user.id, {"url": f"https://s.example.com/{i}"})["id"] for i in range(quota.FREE_CAPS.favorite_targets + 1)]
    for i in ids[:-1]:
        assert client.patch(f"/api/favorites/{i}", json={"target_twd": 100}, headers=h).status_code == 200
    assert client.patch(f"/api/favorites/{ids[-1]}", json={"target_twd": 100}, headers=h).status_code == 429
    assert client.patch(f"/api/favorites/{ids[0]}", json={"target_twd": 50}, headers=h).status_code == 200
