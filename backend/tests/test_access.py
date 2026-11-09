"""擁有者檢查、公開設定白名單、部落格解鎖。"""
import pytest

import db
from crawler.config import CrawlConfig
from jobs import manager


@pytest.fixture
def owner(make_user):
    return make_user()


@pytest.fixture
def other(make_user):
    return make_user()


@pytest.fixture
def run_id(owner):
    rid = "run-private-01"
    db.create_run_record(owner.id, rid, ["kw"], {
        "records": [{"title": "A", "url": "https://x.example.com/a", "price": "NT$100"}],
        "summary": {"total": 1},
    })
    return rid


@pytest.fixture
def job(owner):
    view = manager.create(CrawlConfig(keywords=["kw"]), owner.id)
    with db.SessionLocal() as s:
        s.get(db.Job, view.id).status = "running"
        s.commit()
    return view


# ---------- 匯出 ----------

@pytest.mark.parametrize("fmt", ["csv", "xlsx", "md"])
def test_export_requires_owner(client, run_id, owner, other, bearer, fmt):
    assert client.get(f"/api/export/{run_id}.{fmt}").status_code == 404
    assert client.get(f"/api/export/{run_id}.{fmt}", headers=bearer(other)).status_code == 404
    assert client.get(f"/api/export/{run_id}.{fmt}", headers=bearer(owner)).status_code == 200


def test_export_allowed_once_shared(client, run_id, owner):
    db.set_run_shared(run_id, owner.id, True)
    assert client.get(f"/api/export/{run_id}.csv").status_code == 200


def test_public_share_link_still_works(client, run_id, owner):
    assert client.get(f"/api/share/{run_id}").status_code == 404
    db.set_run_shared(run_id, owner.id, True)
    r = client.get(f"/api/share/{run_id}")
    assert r.status_code == 200 and r.json()["records"][0]["title"] == "A"


def test_admin_can_export(client, run_id, make_user, bearer):
    admin = make_user("admin@example.com", email_verified=True)
    assert client.get(f"/api/export/{run_id}.csv", headers=bearer(admin)).status_code == 200


# ---------- 洞察 / 摘要 / 分頁項目 ----------

def test_insights_run_id_requires_owner(client, run_id, owner, other, bearer):
    body = {"run_id": run_id}
    assert client.post("/api/insights", json=body).status_code == 404
    assert client.post("/api/insights", json=body, headers=bearer(other)).status_code == 404
    assert client.post("/api/insights", json=body, headers=bearer(owner)).status_code == 200


def test_insights_with_client_records_needs_no_login(client):
    r = client.post("/api/insights", json={"records": [{"title": "A", "price": "NT$10"}]})
    assert r.status_code == 200


def test_insights_records_size_capped(client):
    r = client.post("/api/insights", json={"records": [{"title": "x"}] * 2001})
    assert r.status_code == 400


def test_insights_compare_requires_owner(client, run_id, owner, other, bearer):
    assert client.get(f"/api/insights/compare/{run_id}").status_code == 401
    assert client.get(f"/api/insights/compare/{run_id}", headers=bearer(other)).status_code == 404
    assert client.get(f"/api/insights/compare/{run_id}", headers=bearer(owner)).status_code == 200


def test_compare_not_opened_by_share(client, run_id, owner, other, bearer):
    db.set_run_shared(run_id, owner.id, True)
    assert client.get(f"/api/insights/compare/{run_id}", headers=bearer(other)).status_code == 404


def test_summarize_requires_owner(client, run_id, other, bearer):
    assert client.post("/api/summarize", json={"run_id": run_id}, headers=bearer(other)).status_code == 404


def test_summarize_owner_passes_access_check(client, run_id, owner, bearer):
    r = client.post("/api/summarize", json={"run_id": run_id}, headers=bearer(owner))
    assert r.status_code == 200 and r.json()["available"] is False  # 沒有 AI 金鑰


def test_run_items_requires_owner(client, run_id, owner, other, bearer):
    assert client.get(f"/api/run/{run_id}/items", headers=bearer(other)).status_code == 404
    assert client.get(f"/api/run/{run_id}/items", headers=bearer(owner)).status_code == 200


# ---------- 爬蟲任務 ----------

def test_crawl_status_requires_owner(client, job, owner, other, bearer):
    assert client.get(f"/api/crawl/{job.id}").status_code == 401
    assert client.get(f"/api/crawl/{job.id}", headers=bearer(other)).status_code == 404
    assert client.get(f"/api/crawl/{job.id}", headers=bearer(owner)).status_code == 200


def test_crawl_stop_requires_owner(client, job, owner, other, bearer):
    assert client.post(f"/api/crawl/{job.id}/stop").status_code == 401
    assert client.post(f"/api/crawl/{job.id}/stop", headers=bearer(other)).status_code == 404
    assert manager.get(job.id).stop_requested is False
    assert client.post(f"/api/crawl/{job.id}/stop", headers=bearer(owner)).status_code == 200
    assert manager.get(job.id).stop_requested is True


def test_events_require_owner(client, job, owner, other, bearer):
    assert client.get(f"/api/crawl/{job.id}/events").status_code == 401
    assert client.get(f"/api/crawl/{job.id}/events", headers=bearer(other)).status_code == 404
    r = client.get(f"/api/crawl/{job.id}/events", headers=bearer(owner))
    assert r.status_code == 200 and r.json()["events"][0]["type"] == "queued"


# ---------- 公開設定白名單 ----------

def test_public_seo_only_returns_allowlist(client):
    db.save_app_settings({
        "site_title": "Tamon", "site_description": "desc", "keywords": "k", "og_image": "https://x/og.png",
        "ai:openai:key": "enc:v1:secret", "ai:provider": "openai", "internal_flag": "1",
    })
    r = client.get("/api/seo")
    assert r.status_code == 200
    assert r.json() == {"site_title": "Tamon", "site_description": "desc", "keywords": "k", "og_image": "https://x/og.png"}


def test_admin_still_sees_all_settings(client, make_user, bearer):
    db.save_app_settings({"site_title": "Tamon", "internal_flag": "1"})
    admin = make_user("admin@example.com", email_verified=True)
    data = client.get("/api/admin/app-settings", headers=bearer(admin)).json()["settings"]
    assert data["internal_flag"] == "1" and data["site_title"] == "Tamon"


# ---------- 部落格解鎖 ----------

def _post(author, **kw):
    data = {"title": "T", "slug": kw.pop("slug", "t"), "content": "秘密內容", "published": True, **kw}
    return db.create_post(author.id, data)


def test_unlock_correct_password(client, owner):
    p = _post(owner, password="pw123")
    r = client.post(f"/api/blog/{p['id']}/unlock", json={"password": "pw123"})
    assert r.status_code == 200 and r.json()["content"] == "秘密內容"


def test_unlock_wrong_password(client, owner):
    p = _post(owner, password="pw123")
    assert client.post(f"/api/blog/{p['id']}/unlock", json={"password": "nope"}).status_code == 403


def test_unlock_passwordless_post_returns_nothing(client, owner):
    p = _post(owner)
    r = client.post(f"/api/blog/{p['id']}/unlock", json={"password": ""})
    assert r.status_code == 403 and "content" not in r.json()


def test_unlock_draft_never_returned(client, owner):
    p = _post(owner, password="pw123", published=False)
    assert client.post(f"/api/blog/{p['id']}/unlock", json={"password": "pw123"}).status_code == 403


def test_unlock_rate_limited(client, owner):
    p = _post(owner, password="pw123")
    codes = [client.post(f"/api/blog/{p['id']}/unlock", json={"password": "x"}).status_code for _ in range(11)]
    assert codes[:10] == [403] * 10 and codes[10] == 429
