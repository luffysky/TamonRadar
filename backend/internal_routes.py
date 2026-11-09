"""內部端點:給 Vercel Cron 與自我觸發呼叫,一律需要 Bearer CRON_SECRET(沒設就拒絕)。"""
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException

import scheduler
import worker

router = APIRouter(prefix="/api/internal", tags=["internal"])


def require_cron(authorization: str | None = Header(default=None)) -> None:
    secret = (os.environ.get("CRON_SECRET") or "").strip()
    if not secret:
        raise HTTPException(503, "未設定 CRON_SECRET,內部端點停用")
    if not hmac.compare_digest((authorization or "").encode(), f"Bearer {secret}".encode()):
        raise HTTPException(401, "unauthorized")


# Vercel Cron 用 GET;自我觸發用 POST

@router.api_route("/worker", methods=["GET", "POST"])
def run_worker(_auth: None = Depends(require_cron)):
    return worker.run()


@router.api_route("/dispatch", methods=["GET", "POST"])
def run_dispatch(_auth: None = Depends(require_cron)):
    counts = scheduler.dispatch()
    if scheduler.fired_anything(counts):
        worker.trigger()   # 不等下一分鐘的 worker cron
    return {"ok": True, "counts": counts}
