"""Web Push(瀏覽器系統通知):用 VAPID 金鑰 + pywebpush。

設了 VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY 才會啟用;沒設則全部靜默跳過。
產生金鑰:`python -c "from py_vapid import Vapid01 as V; v=V(); v.generate_keys(); ..."` 或線上工具。
"""
import json
import os


def public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def available() -> bool:
    return bool(os.environ.get("VAPID_PRIVATE_KEY") and os.environ.get("VAPID_PUBLIC_KEY"))


def send_to_user(user_id: int, title: str, body: str = "", url: str = "") -> None:
    if not available():
        return
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return
    import db
    subs = db.list_push_subs(user_id)
    if not subs:
        return
    priv = os.environ.get("VAPID_PRIVATE_KEY", "")
    claims_sub = os.environ.get("VAPID_SUBJECT", "mailto:admin@tamonradar.app")
    payload = json.dumps({"title": title, "body": body[:300], "url": url})
    for s in subs:
        try:
            webpush(
                subscription_info={"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}},
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": claims_sub},
            )
        except WebPushException as e:
            # 410 Gone / 404 → 訂閱失效,刪掉
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                db.remove_push_sub(s["endpoint"])
        except Exception:
            pass
