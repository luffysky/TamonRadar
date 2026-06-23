"""認證:密碼雜湊(pbkdf2,純標準庫)+ JWT token。"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import SessionLocal, User

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-secret-change-me")
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

def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return int(payload["sub"])
    except Exception:
        return None


# ---------- OAuth state(防 CSRF 的短效簽章值)----------

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

def create_reset_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "typ": "pwreset",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_reset_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("typ") != "pwreset":
            return None
        return int(payload["sub"])
    except Exception:
        return None


# ---------- FastAPI 依賴 ----------

def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if cred is None:
        raise HTTPException(401, "需要登入")
    user_id = _decode(cred.credentials)
    if user_id is None:
        raise HTTPException(401, "登入已失效,請重新登入")
    with SessionLocal() as s:
        user = s.get(User, user_id)
    if user is None:
        raise HTTPException(401, "使用者不存在")
    return user
