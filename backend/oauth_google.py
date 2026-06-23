"""Google 第三方登入(OAuth 2.0 Authorization Code flow,手刻、不依賴額外套件)。

流程:前端 → /api/auth/google/login → Google 登入頁 → /api/auth/google/callback
→ 後端用 code 換 token、取 email、建立/找到使用者、發我們自己的 JWT
→ 轉址回前端 /auth/callback#token=...,前端存起來即完成登入。
"""
import os
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

import auth
import db

router = APIRouter()

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"


def _cfg() -> tuple[str | None, str | None]:
    return os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")


CALLBACK_PATH = "/api/auth/google/callback"


def _redirect_uri(request: Request) -> str:
    base = (os.environ.get("OAUTH_REDIRECT_BASE") or str(request.base_url)).strip().rstrip("/")
    # 容錯:若有人把整段 callback 路徑也填進 OAUTH_REDIRECT_BASE,去掉它避免重複
    if base.endswith(CALLBACK_PATH):
        base = base[: -len(CALLBACK_PATH)].rstrip("/")
    return f"{base}{CALLBACK_PATH}"


def _frontend() -> str:
    fe = os.environ.get("FRONTEND_URL")
    if fe:
        return fe.rstrip("/")
    cors = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    return cors.split(",")[0].strip().rstrip("/")


@router.get("/api/auth/google/login")
def google_login(request: Request):
    cid, secret = _cfg()
    if not cid or not secret:
        raise HTTPException(400, "後端尚未設定 Google OAuth(GOOGLE_CLIENT_ID/SECRET)")
    params = urlencode({
        "client_id": cid,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": auth.create_state(),
        "access_type": "online",
        "prompt": "select_account",
    })
    return RedirectResponse(f"{GOOGLE_AUTH}?{params}")


@router.get("/api/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = ""):
    fe = _frontend()
    cid, secret = _cfg()

    if not auth.verify_state(state):
        return RedirectResponse(f"{fe}/auth/callback#error=state")
    if not code or not cid or not secret:
        return RedirectResponse(f"{fe}/auth/callback#error=config")

    try:
        token_resp = requests.post(GOOGLE_TOKEN, data={
            "code": code,
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": _redirect_uri(request),
            "grant_type": "authorization_code",
        }, timeout=20).json()
        access = token_resp.get("access_token")
        if not access:
            return RedirectResponse(f"{fe}/auth/callback#error=token")

        info = requests.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access}"},
            timeout=20,
        ).json()
        email = (info.get("email") or "").strip().lower()
        if not email:
            return RedirectResponse(f"{fe}/auth/callback#error=email")
    except Exception:
        return RedirectResponse(f"{fe}/auth/callback#error=oauth")

    with db.SessionLocal() as s:
        user = s.scalar(select(db.User).where(db.User.email == email))
        if user is None:
            user = db.User(email=email, password_hash="", provider="google")
            s.add(user)
            s.commit()
            s.refresh(user)
        jwt_token = auth.create_token(user.id)

    return RedirectResponse(f"{fe}/auth/callback#token={jwt_token}")
