"""測試環境:在匯入任何 app 程式前,強制使用暫存 SQLite 與假密鑰,並擋掉真實網路。

設定 TAMON_PG_TEST_URL 可改跑真實 Postgres(網址必須帶 options=-csearch_path=pytest_xxx,確保只動專用 schema)。
"""
import os
import socket
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="tamon_test_")
_PG_URL = os.environ.get("TAMON_PG_TEST_URL", "").strip()
if _PG_URL:
    assert "search_path" in _PG_URL and "pytest_" in _PG_URL, "Postgres 測試必須指定 pytest_ 開頭的專用 schema"
_FORCED_ENV = {
    "DATABASE_URL": _PG_URL or f"sqlite:///{Path(_TMP, 'test.db').as_posix()}",
    "CRON_SECRET": "test-cron-secret",
    "WORKER_TRIGGER_BASE": "",
    "VERCEL_URL": "",
    "VERCEL_PROJECT_PRODUCTION_URL": "",
    "VERCEL": "",
    "APP_ENV": "test",
    "JWT_SECRET": "test-jwt-secret-not-real-0123456789abcdef",
    "ENCRYPTION_KEY": "test-encryption-key-not-real",
    "ENCRYPTION_KEY_PREVIOUS": "",
    "ADMIN_EMAILS": "admin@example.com",
    "OWNER_EMAILS": "",
    "ADMIN_TRUSTED_USER_IDS": "",
    "TELEGRAM_WEBHOOK_SECRET": "",
    "TRUSTED_IP_HEADER": "",
    "FREE_AI_DAILY": "30",
    "FREE_SEARCH_DAILY": "15",
    "DISABLE_BROWSER": "1",
}
_CLEARED_ENV = (
    "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
    "SERPAPI_KEY", "BRAVE_API_KEY", "SERPER_API_KEY", "GOOGLE_CSE_KEY", "TAVILY_API_KEY", "SEARXNG_URL",
    "TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN", "DISCORD_PUBLIC_KEY", "DISCORD_WEBHOOK",
    "RESEND_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD", "ENV",
    "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "VAPID_PRIVATE_KEY",
)
os.environ.update(_FORCED_ENV)
for _k in _CLEARED_ENV:
    os.environ.pop(_k, None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

import db  # noqa: E402

assert bool(_PG_URL) or (db.IS_SQLITE and _TMP.replace("\\", "/") in db._url.replace("\\", "/")), "測試必須使用暫存 SQLite"


if db.IS_SQLITE:
    @event.listens_for(db.engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):
        # SQLite 預設不檢查外鍵;打開才測得出 Postgres 上會發生的 FK 失敗
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


import app as app_module  # noqa: E402
import auth  # noqa: E402
import ratelimit  # noqa: E402

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
if _PG_URL:   # 真實 Postgres 模式:psycopg 用 Python 解析主機名,要放行資料庫這一台
    from urllib.parse import urlsplit
    _LOOPBACK.add(urlsplit(_PG_URL).hostname)
_real_connect = socket.socket.connect
_real_getaddrinfo = socket.getaddrinfo


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """任何對外連線都直接失敗;本機 loopback 僅供 asyncio 內部使用。"""

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOOPBACK:
            raise AssertionError(f"測試不可連線到外部:{host}")
        return _real_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host in _LOOPBACK or host is None:
            return _real_getaddrinfo(host, *args, **kwargs)
        raise socket.gaierror(f"測試不可查詢外部 DNS:{host}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


@pytest.fixture(autouse=True)
def fresh_state():
    if db.IS_SQLITE:
        db.Base.metadata.drop_all(db.engine)
        db.init_db()
    else:
        _reset_postgres()
    ratelimit.reset()
    yield


_pg_ready = False


def _reset_postgres():
    global _pg_ready
    with db.engine.begin() as conn:
        if not _pg_ready:
            db.Base.metadata.create_all(conn)
            _pg_ready = True
        names = ", ".join(t.name for t in db.Base.metadata.sorted_tables)
        conn.exec_driver_sql(f"TRUNCATE {names} RESTART IDENTITY CASCADE")


@pytest.fixture
def client():
    # 不用 with:不觸發 startup,測試不啟動排程器
    return TestClient(app_module.app, raise_server_exceptions=True)


@pytest.fixture
def make_user():
    counter = {"n": 0}

    def _make(email=None, **kw):
        counter["n"] += 1
        email = email or f"user{counter['n']}@example.com"
        with db.SessionLocal() as s:
            u = db.User(email=email, password_hash=kw.pop("password_hash", ""), username=email.split("@")[0], **kw)
            s.add(u)
            s.commit()
            s.refresh(u)
            return u

    return _make


@pytest.fixture
def bearer():
    def _bearer(user):
        return {"Authorization": f"Bearer {auth.create_token(user.id, user.token_version or 0)}"}

    return _bearer


@pytest.fixture
def public_dns(monkeypatch):
    """把所有網域解析成一個公網 IP。"""
    import safe_fetch
    monkeypatch.setattr(safe_fetch, "_resolve", lambda host, port: ["93.184.216.34"])
