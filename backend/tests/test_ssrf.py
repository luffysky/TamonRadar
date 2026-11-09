import io
import socket

import pytest
import requests

import db
import safe_fetch
from safe_fetch import ResponseTooLarge, UnsafeURLError, validate_url


def fake_resolve(monkeypatch, mapping):
    def getaddrinfo(host, port, *a, **k):
        if host not in mapping:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in mapping[host]]

    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", getaddrinfo)


def make_response(status=200, body=b"<html>ok</html>", headers=None, url="http://example.com/"):
    r = requests.Response()
    r.status_code = status
    r.url = url
    r.headers.update(headers or {})
    r.raw = io.BytesIO(body)
    return r


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "127.1.2.3", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "0.0.0.0",
    "100.64.0.1", "224.0.0.1", "168.63.129.16", "::1", "fc00::1", "fe80::1", "::ffff:127.0.0.1",
    "::ffff:169.254.169.254", "64:ff9b::7f00:1", "2002:7f00:1::",
])
def test_private_ips_blocked(ip):
    assert safe_fetch._ip_is_public(ip) is False


@pytest.mark.parametrize("ip", ["8.8.8.8", "93.184.216.34", "2606:4700:4700::1111"])
def test_public_ips_allowed(ip):
    assert safe_fetch._ip_is_public(ip) is True


@pytest.mark.parametrize("url", [
    "ftp://example.com/x", "file:///etc/passwd", "gopher://example.com", "javascript:alert(1)", "",
    "http://user:pw@example.com/", "http://exa\\mple.com/", "http://example.com/a\nb", "http://", "http://" + "a" * 1100,
])
def test_invalid_urls_rejected(url):
    with pytest.raises(UnsafeURLError):
        validate_url(url, resolve=False)


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://localhost/", "http://svc.internal/"])
def test_literal_private_rejected_without_dns(url):
    with pytest.raises(UnsafeURLError):
        validate_url(url, resolve=False)


def test_public_domain_passes_after_dns(monkeypatch):
    fake_resolve(monkeypatch, {"shop.example.com": ["93.184.216.34"]})
    assert validate_url("https://shop.example.com/item") == "https://shop.example.com/item"


def test_domain_resolving_to_private_ip_rejected(monkeypatch):
    fake_resolve(monkeypatch, {"evil.example.com": ["169.254.169.254"]})
    with pytest.raises(UnsafeURLError):
        validate_url("http://evil.example.com/")


def test_domain_with_any_private_address_rejected(monkeypatch):
    fake_resolve(monkeypatch, {"mixed.example.com": ["93.184.216.34", "10.0.0.1"]})
    with pytest.raises(UnsafeURLError):
        validate_url("http://mixed.example.com/")


def test_redirect_to_private_blocked_and_never_fetched(monkeypatch):
    fake_resolve(monkeypatch, {"a.example.com": ["93.184.216.34"]})
    calls = []

    def fake_open(session, url, headers, timeout):
        calls.append(url)
        return make_response(302, b"", {"Location": "http://169.254.169.254/latest/"})

    monkeypatch.setattr(safe_fetch, "_open", fake_open)
    with pytest.raises(UnsafeURLError):
        safe_fetch.safe_get("http://a.example.com/")
    assert calls == ["http://a.example.com/"]


def test_redirect_each_hop_validated_then_body_returned(monkeypatch):
    fake_resolve(monkeypatch, {"a.example.com": ["93.184.216.34"], "b.example.com": ["93.184.216.35"]})

    def fake_open(session, url, headers, timeout):
        if url.startswith("http://a."):
            return make_response(301, b"", {"Location": "http://b.example.com/final"})
        return make_response(200, b"hello", url=url)

    monkeypatch.setattr(safe_fetch, "_open", fake_open)
    resp = safe_fetch.safe_get("http://a.example.com/")
    assert resp.text == "hello"
    assert resp.status_code == 200


def test_too_many_redirects(monkeypatch):
    fake_resolve(monkeypatch, {"a.example.com": ["93.184.216.34"]})
    monkeypatch.setattr(safe_fetch, "_open", lambda *a: make_response(302, b"", {"Location": "http://a.example.com/next"}))
    with pytest.raises(UnsafeURLError):
        safe_fetch.safe_get("http://a.example.com/")


def test_size_limit_by_header(monkeypatch):
    fake_resolve(monkeypatch, {"a.example.com": ["93.184.216.34"]})
    monkeypatch.setattr(safe_fetch, "_open", lambda *a: make_response(200, b"x", {"Content-Length": "99999999"}))
    with pytest.raises(ResponseTooLarge):
        safe_fetch.safe_get("http://a.example.com/", max_bytes=1000)


def test_size_limit_while_streaming(monkeypatch):
    fake_resolve(monkeypatch, {"a.example.com": ["93.184.216.34"]})
    monkeypatch.setattr(safe_fetch, "_open", lambda *a: make_response(200, b"x" * 5000))
    with pytest.raises(ResponseTooLarge):
        safe_fetch.safe_get("http://a.example.com/", max_bytes=1000)


def test_dns_rebinding_blocked_at_connect(monkeypatch):
    """驗證時是公網、實際連線時變內網:連線層要擋下,而且絕不建立 socket。"""
    fake_resolve(monkeypatch, {"rebind.example.com": ["127.0.0.1"]})
    called = []
    monkeypatch.setattr(safe_fetch._u3_connection, "create_connection", lambda *a, **k: called.append(a))
    conn = safe_fetch._SafeHTTPConnection("rebind.example.com", 80)
    with pytest.raises(UnsafeURLError):
        conn._new_conn()
    assert called == []


def test_connection_pins_validated_ip_and_keeps_hostname(monkeypatch):
    fake_resolve(monkeypatch, {"shop.example.com": ["93.184.216.34"]})
    seen = {}

    def fake_create(address, *a, **k):
        seen["address"] = address
        return object()

    monkeypatch.setattr(safe_fetch._u3_connection, "create_connection", fake_create)
    conn = safe_fetch._SafeHTTPSConnection("shop.example.com", 443)
    conn._new_conn()
    assert seen["address"] == ("93.184.216.34", 443)
    assert conn.host == "shop.example.com"  # SNI / 憑證驗證仍用網域


def test_session_ignores_env_proxy_and_mounts_safe_adapter():
    session = safe_fetch._new_session()
    assert session.trust_env is False
    adapter = session.get_adapter("https://example.com/")
    assert adapter.poolmanager.pool_classes_by_scheme["https"] is safe_fetch._SafeHTTPSPool
    assert adapter.poolmanager.pool_classes_by_scheme["http"] is safe_fetch._SafeHTTPPool


# ---------- API 入口 ----------

@pytest.mark.parametrize("path,body", [
    ("/api/scrape-page", {"url": "http://169.254.169.254/latest/"}),
    ("/api/crawl-site", {"url": "http://127.0.0.1:8000/"}),
    ("/api/watches", {"url": "http://192.168.0.1/admin"}),
])
def test_endpoints_reject_private_urls_and_dont_charge_quota(client, make_user, bearer, path, body):
    user = make_user()
    r = client.post(path, json=body, headers=bearer(user))
    assert r.status_code == 400
    assert db.quota_today(user.id)["search"] == 0


def test_watch_update_also_validated(client, make_user, bearer, public_dns):
    user = make_user()
    created = client.post("/api/watches", json={"url": "https://shop.example.com/a", "interval_minutes": 30}, headers=bearer(user))
    assert created.status_code == 200
    r = client.patch(f"/api/watches/{created.json()['id']}", json={"url": "file:///etc/passwd"}, headers=bearer(user))
    assert r.status_code == 400


def test_favorite_rejects_internal_url(client, make_user, bearer):
    r = client.post("/api/favorites", json={"url": "http://127.0.0.1/secret"}, headers=bearer(make_user()))
    assert r.status_code == 400


def test_discord_webhook_must_be_discord(client, make_user, bearer):
    r = client.put("/api/settings", json={"discord_webhook": "http://169.254.169.254/x"}, headers=bearer(make_user()))
    assert r.status_code == 400


def test_notify_refuses_non_discord_webhook(monkeypatch):
    import notify
    monkeypatch.setattr(notify.requests, "post", lambda *a, **k: pytest.fail("不應送出"))
    ok, _ = notify.send_discord("http://10.0.0.1/hook", content="x")
    assert ok is False


def test_robots_uses_safe_fetch(monkeypatch):
    from crawler import robots
    seen = []

    def fake(url, **k):
        seen.append(url)
        raise UnsafeURLError("blocked")

    monkeypatch.setattr(robots, "safe_get", fake)
    robots._cache.clear()
    assert robots.allowed("http://169.254.169.254/x") is True  # 抓不到 robots 視為允許,實際抓取由 safe_get 擋
    assert seen == ["http://169.254.169.254/robots.txt"]


def test_site_crawler_stops_on_unsafe_url(monkeypatch):
    from crawler import robots, site_crawler
    from crawler.config import CrawlConfig
    monkeypatch.setattr(robots, "allowed", lambda u: True)
    monkeypatch.setattr(site_crawler, "safe_get", lambda *a, **k: (_ for _ in ()).throw(UnsafeURLError("blocked")))
    events = []
    res = site_crawler.run_site_crawl(CrawlConfig(site_url="http://10.0.0.1/", site_max_pages=3), on_event=events.append)
    assert res["total"] == 0
    assert any(e["type"] == "warning" for e in events)
