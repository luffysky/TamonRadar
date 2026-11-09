"""正式環境設定、加解密、管理員判定、密碼流程、限流、webhook。"""
from types import SimpleNamespace

import pytest

import appconfig
import auth
import bots
import crypto
import db
import oauth_google
import ratelimit


def set_env(monkeypatch, **env):
    for k in ("APP_ENV", "ENV", "DATABASE_URL", "JWT_SECRET", "ENCRYPTION_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


# ---------- 正式環境 fail-closed ----------

@pytest.mark.parametrize("env,prod", [
    ({"APP_ENV": "production"}, True), ({"APP_ENV": "prod"}, True), ({"ENV": "production"}, True),
    ({"APP_ENV": "development", "DATABASE_URL": "postgresql://h/db"}, False),
    ({"DATABASE_URL": "postgresql://h/db"}, True), ({"DATABASE_URL": "postgres://h/db"}, True),
    ({"DATABASE_URL": "sqlite:///x.db"}, False), ({}, False),
])
def test_is_production(monkeypatch, env, prod):
    set_env(monkeypatch, **env)
    assert appconfig.is_production() is prod


@pytest.mark.parametrize("env", [
    {"APP_ENV": "production"},
    {"APP_ENV": "production", "JWT_SECRET": "a" * 40},
    {"APP_ENV": "production", "ENCRYPTION_KEY": "b" * 40},
    {"APP_ENV": "production", "JWT_SECRET": appconfig.DEV_JWT_SECRET, "ENCRYPTION_KEY": "b" * 40},
    {"APP_ENV": "production", "JWT_SECRET": "a" * 40, "ENCRYPTION_KEY": appconfig.DEV_ENCRYPTION_KEY},
    {"APP_ENV": "production", "JWT_SECRET": "same" * 10, "ENCRYPTION_KEY": "same" * 10},
])
def test_production_refuses_bad_secrets(monkeypatch, env):
    set_env(monkeypatch, **env)
    with pytest.raises(RuntimeError):
        appconfig.assert_production_config()


def test_production_error_does_not_leak_values(monkeypatch):
    set_env(monkeypatch, APP_ENV="production", JWT_SECRET="super-secret-value", ENCRYPTION_KEY="super-secret-value")
    with pytest.raises(RuntimeError) as e:
        appconfig.assert_production_config()
    assert "super-secret-value" not in str(e.value)


def test_production_accepts_good_secrets(monkeypatch):
    set_env(monkeypatch, APP_ENV="production", JWT_SECRET="a" * 40, ENCRYPTION_KEY="b" * 40)
    appconfig.assert_production_config()


def test_dev_allows_missing_secrets(monkeypatch):
    set_env(monkeypatch, APP_ENV="development")
    appconfig.assert_production_config()


# ---------- 加解密 ----------

def test_decrypt_failure_raises_not_empty(monkeypatch):
    token = crypto.encrypt("sk-value")
    monkeypatch.setenv("ENCRYPTION_KEY", "a-different-key")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token)


def test_previous_key_still_decrypts(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "old-key")
    token = crypto.encrypt("sk-value")
    monkeypatch.setenv("ENCRYPTION_KEY", "new-key")
    monkeypatch.setenv("ENCRYPTION_KEY_PREVIOUS", "older-key, old-key")
    assert crypto.decrypt(token) == "sk-value"


def test_legacy_plaintext_passthrough():
    assert crypto.decrypt("plain") == "plain"


def test_rotation_mistake_does_not_wipe_settings(monkeypatch, make_user):
    user = make_user()
    db.save_settings(user.id, {"openai_key": "sk-original"})
    monkeypatch.setenv("ENCRYPTION_KEY", "wrong-key")

    st = db.get_settings(user.id)
    assert st["openai_key"] == "" and st["decrypt_failed"] == ["openai_key"]

    # 前端把讀到的空字串原樣存回來:密文要保留
    db.save_settings(user.id, {"openai_key": ""})
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key-not-real")
    assert db.get_settings(user.id)["openai_key"] == "sk-original"


def test_ai_config_reports_decrypt_failure(monkeypatch):
    db.save_ai_config("openai", {"key": "sk-admin-key-123456"})
    monkeypatch.setenv("ENCRYPTION_KEY", "wrong-key")
    info = db.get_ai_config(masked=True)["providers"]["openai"]
    assert info["decrypt_failed"] is True and info["has_key"] is False
    assert db.ai_db_setting("openai", "key") == ""


# ---------- 管理員 ----------

def test_unverified_admin_email_is_not_admin(client, make_user, bearer):
    fake = make_user("admin@example.com")
    assert auth.is_admin(fake) is False
    assert client.get("/api/admin/stats", headers=bearer(fake)).status_code == 403


def test_verified_admin_allowed(client, make_user, bearer):
    admin = make_user("admin@example.com", email_verified=True)
    assert auth.is_admin(admin) is True
    assert client.get("/api/admin/stats", headers=bearer(admin)).status_code == 200


def test_google_admin_allowed(make_user):
    assert auth.is_admin(make_user("admin@example.com", provider="google")) is True


def test_trusted_user_id_keeps_existing_admin(monkeypatch, make_user):
    existing = make_user("admin@example.com")
    monkeypatch.setenv("ADMIN_TRUSTED_USER_IDS", f"999, {existing.id}")
    assert auth.is_admin(existing) is True


def test_trusted_id_needs_listed_email(monkeypatch, make_user):
    user = make_user("notadmin@example.com", email_verified=True)
    monkeypatch.setenv("ADMIN_TRUSTED_USER_IDS", str(user.id))
    assert auth.is_admin(user) is False


def test_owner_requires_verified(monkeypatch, make_user):
    monkeypatch.setenv("OWNER_EMAILS", "owner@example.com")
    assert auth.is_owner(make_user("owner@example.com")) is False
    with db.SessionLocal() as s:
        s.query(db.User).delete()
        s.commit()
    assert auth.is_owner(make_user("owner@example.com", email_verified=True)) is True


def test_me_reports_real_admin_state(client, make_user, bearer):
    fake = make_user("admin@example.com")
    assert client.get("/api/auth/me", headers=bearer(fake)).json()["user"]["is_admin"] is False


# ---------- 密碼 / JWT ----------

def _local_user(make_user, email="u@example.com", password="secret1"):
    return make_user(email, password_hash=auth.hash_password(password))


def test_password_change_invalidates_old_tokens(client, make_user, bearer):
    user = _local_user(make_user)
    old = bearer(user)
    r = client.post("/api/auth/change-password", json={"current_password": "secret1", "new_password": "newpass1"}, headers=old)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 200


def test_legacy_token_without_version_still_valid_until_change(client, make_user):
    import jwt
    from datetime import datetime, timedelta, timezone
    user = _local_user(make_user)
    legacy = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(days=1)}, auth.JWT_SECRET, algorithm=auth.JWT_ALGO)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 200


def test_reset_token_single_use(client, make_user):
    user = _local_user(make_user)
    token = auth.create_reset_token(user.id, user.token_version)
    assert client.post("/api/auth/reset", json={"token": token, "password": "brandnew1"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": token, "password": "hacked99"}).status_code == 400
    assert client.post("/api/auth/login", json={"email": user.email, "password": "brandnew1"}).status_code == 200


def test_reset_invalidates_existing_sessions(client, make_user, bearer):
    user = _local_user(make_user)
    old = bearer(user)
    token = auth.create_reset_token(user.id, user.token_version)
    client.post("/api/auth/reset", json={"token": token, "password": "brandnew1"})
    assert client.get("/api/auth/me", headers=old).status_code == 401


def test_password_change_kills_outstanding_reset_token(client, make_user, bearer):
    user = _local_user(make_user)
    token = auth.create_reset_token(user.id, user.token_version)
    client.post("/api/auth/change-password", json={"current_password": "secret1", "new_password": "newpass1"}, headers=bearer(user))
    assert client.post("/api/auth/reset", json={"token": token, "password": "hacked99"}).status_code == 400


@pytest.mark.parametrize("maker", [auth.create_reset_token, auth.create_verify_token])
def test_special_tokens_cannot_login(client, make_user, maker):
    user = _local_user(make_user)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {maker(user.id)}"})
    assert r.status_code == 401


def test_banned_user_treated_as_anonymous_on_optional_routes(make_user):
    user = make_user(banned=True)
    token = auth.create_token(user.id, 0)
    assert auth.get_optional_user(SimpleNamespace(credentials=token)) is None


# ---------- 限流 ----------

def test_limiter_window():
    assert all(ratelimit.hit("k", 3, 60) for _ in range(3))
    assert ratelimit.hit("k", 3, 60) is False
    assert ratelimit.hit("other", 3, 60) is True


def test_login_rate_limited_per_email(client, make_user):
    user = _local_user(make_user)
    codes = [client.post("/api/auth/login", json={"email": user.email, "password": "bad"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_register_rate_limited_per_ip(client):
    codes = [client.post("/api/auth/register", json={"email": f"n{i}@example.com", "password": "secret1"}).status_code for i in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


def test_forgot_rate_limited_per_ip(client):
    codes = [client.post("/api/auth/forgot", json={"email": f"n{i}@example.com"}).status_code for i in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


def test_forgot_per_email_silently_stops_sending(client, make_user, monkeypatch):
    import mailer
    user = _local_user(make_user)
    sent = []
    monkeypatch.setattr(mailer, "mail_available", lambda: True)
    monkeypatch.setattr(mailer, "send_email", lambda to, subj, html: sent.append(to) or (True, "ok"))
    for _ in range(5):
        assert client.post("/api/auth/forgot", json={"email": user.email}).status_code == 200
    assert len(sent) == 3


def test_reset_rate_limited(client):
    codes = [client.post("/api/auth/reset", json={"token": "bad", "password": "secret1"}).status_code for _ in range(11)]
    assert codes[:10] == [400] * 10 and codes[10] == 429


def test_spoofed_forwarded_header_cannot_bypass_ip_limit(client):
    codes = [client.post("/api/auth/reset", json={"token": "bad", "password": "secret1"},
                         headers={"X-Forwarded-For": f"1.2.3.{i}, 9.9.9.9"}).status_code for i in range(11)]
    assert codes[10] == 429


# ---------- Webhook ----------

def test_telegram_webhook_fails_closed_when_unset(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(bots, "handle_telegram", lambda u: pytest.fail("不應處理"))
    assert client.post("/api/telegram/webhook/tamon", json={}).status_code == 403


def test_telegram_webhook_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "right-secret")
    monkeypatch.setattr(bots, "handle_telegram", lambda u: pytest.fail("不應處理"))
    assert client.post("/api/telegram/webhook/wrong", json={}).status_code == 403


def test_telegram_webhook_accepts_right_secret(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "right-secret")
    calls = []
    monkeypatch.setattr(bots, "handle_telegram", calls.append)
    assert client.post("/api/telegram/webhook/right-secret", json={"update_id": 1}).status_code == 200
    assert len(calls) == 1


def test_set_webhook_refuses_without_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    assert bots.telegram_set_webhook("https://x.example.com")["ok"] is False


def test_discord_fails_closed_when_unset(client, monkeypatch):
    monkeypatch.delenv("DISCORD_PUBLIC_KEY", raising=False)
    assert client.post("/api/discord/interactions", content=b"{}", headers={
        "X-Signature-Ed25519": "00", "X-Signature-Timestamp": "1"}).status_code == 401


# ---------- Google 登入 ----------

@pytest.fixture
def google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("FRONTEND_URL", "https://fe.example.com")
    info = {"email": "victim@example.com", "verified_email": True, "name": "V"}
    monkeypatch.setattr(oauth_google.requests, "post", lambda *a, **k: SimpleNamespace(json=lambda: {"access_token": "tok"}))
    monkeypatch.setattr(oauth_google.requests, "get", lambda *a, **k: SimpleNamespace(json=lambda: info))
    return info


def callback(client):
    return client.get("/api/auth/google/callback", params={"code": "c", "state": auth.create_state()}, follow_redirects=False)


def test_google_refuses_unverified_local_account(client, make_user, google):
    make_user("victim@example.com", password_hash=auth.hash_password("attacker1"))
    r = callback(client)
    assert r.headers["location"].endswith("#error=unverified_local")


def test_google_links_verified_local_account(client, make_user, google):
    make_user("victim@example.com", email_verified=True)
    assert "#token=" in callback(client).headers["location"]


def test_google_new_account_marked_verified(client, google):
    assert "#token=" in callback(client).headers["location"]
    with db.SessionLocal() as s:
        u = s.query(db.User).filter_by(email="victim@example.com").one()
    assert u.email_verified is True and u.provider == "google"


def test_google_rejects_unverified_google_email(client, google):
    google["verified_email"] = False
    assert callback(client).headers["location"].endswith("#error=unverified")
