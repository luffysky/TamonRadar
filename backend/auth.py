"""認證:密碼雜湊(pbkdf2,純標準庫)+ JWT token。"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from appconfig import DEV_JWT_SECRET, assert_production_config
from db import SessionLocal, User

# 正式環境缺密鑰就拒絕啟動,絕不退回開發預設值
assert_production_config()
JWT_SECRET = os.environ.get("JWT_SECRET", DEV_JWT_SECRET)
JWT_ALGO = "HS256"
TOKEN_TTL_DAYS = 14
_PBKDF2_ITERATIONS = 200_000

_bearer = HTTPBearer(auto_error=False)


# ---------- 密碼 ----------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------- JWT ----------

def create_token(user_id: int, token_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "ver": int(token_version or 0),  # 改密碼後 version 會 +1,舊 JWT 就失效
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode(token: str) -> tuple[int, int] | None:
    """回傳 (user_id, token_version);舊版 token 沒有 ver 視為 0。"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("typ"):  # 重設密碼/驗證信等專用 token 不能拿來當登入憑證
            return None
        return int(payload["sub"]), int(payload.get("ver", 0))
    except Exception:
        return None


def _user_from_token(token: str) -> User | None:
    decoded = _decode(token)
    if decoded is None:
        return None
    user_id, version = decoded
    with SessionLocal() as s:
        user = s.get(User, user_id)
    if user is None or (user.token_version or 0) != version:
        return None
    return user


# ---------- OAuth state ----------

def create_state() -> str:
    payload = {
        "typ": "oauth_state",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_state(state: str) -> bool:
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload.get("typ") == "oauth_state"
    except Exception:
        return False


# ---------- 密碼重設 token(短效)----------

def create_reset_token(user_id: int, token_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "typ": "pwreset",
        "ver": int(token_version or 0),  # 重設成功後 version 會變,同一張 token 就不能再用
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_reset_token(token: str) -> tuple[int, int] | None:
    """回傳 (user_id, token_version);由 db.reset_password 依 version 原子地確保只能用一次。"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("typ") != "pwreset":
            return None
        return int(payload["sub"]), int(payload.get("ver", 0))
    except Exception:
        return None


def create_verify_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "typ": "emailverify",
        "exp": datetime.now(timezone.utc) + timedelta(days=3),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_email_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("typ") != "emailverify":
            return None
        return int(payload["sub"])
    except Exception:
        return None


# ---------- FastAPI 依賴 ----------

def _env_emails(name: str) -> set[str]:
    return {e.strip().lower() for e in os.environ.get(name, "").split(",") if e.strip()}


def _env_user_ids(name: str) -> set[int]:
    return {int(x) for x in os.environ.get(name, "").split(",") if x.strip().isdigit()}


def is_email_verified(user) -> bool:
    """本機帳號需點過驗證信;第三方登入(Google)的 email 已由對方驗證。"""
    return bool(getattr(user, "email_verified", False)) or (getattr(user, "provider", "local") or "local") != "local"


def _trusted_identity(user) -> bool:
    """email 名單只代表「這個 email」,還要確認帳號真的擁有它(否則任何人都能搶先註冊管理員 email)。

    既有的未驗證管理員帳號可用 ADMIN_TRUSTED_USER_IDS(使用者 id,由擁有者在環境變數設定)放行。
    """
    return is_email_verified(user) or user.id in _env_user_ids("ADMIN_TRUSTED_USER_IDS")


def is_admin(user) -> bool:
    if user is None or not user.email or user.email.lower() not in _env_emails("ADMIN_EMAILS"):
        return False
    return _trusted_identity(user)


def is_owner(user) -> bool:
    """擁有者(超級管理員)。未設 OWNER_EMAILS 時,管理員即視為擁有者(向後相容)。"""
    owners = _env_emails("OWNER_EMAILS")
    if not owners:
        return is_admin(user)
    if user is None or not user.email or user.email.lower() not in owners:
        return False
    return _trusted_identity(user)


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if cred is None:
        raise HTTPException(401, "需要登入")
    user = _user_from_token(cred.credentials)
    if user is None:
        raise HTTPException(401, "登入已失效,請重新登入")
    if getattr(user, "banned", False):
        raise HTTPException(403, "此帳號已被停權")
    return user


def get_optional_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User | None:
    """有帶有效 token 就回使用者,否則回 None(不強制登入);停權帳號視同未登入。"""
    if cred is None:
        return None
    user = _user_from_token(cred.credentials)
    if user is None or getattr(user, "banned", False):
        return None
    return user


def get_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(403, "需要管理員權限")
    return user


def get_owner(user: User = Depends(get_current_user)) -> User:
    if not is_owner(user):
        raise HTTPException(403, "需要擁有者權限")
    return user
