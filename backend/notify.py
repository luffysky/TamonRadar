"""推播通知:Discord Webhook 與 Telegram Bot。"""
import requests


def send_discord(webhook: str, content: str) -> tuple[bool, str]:
    if not webhook:
        return False, "未設定 Discord webhook"
    try:
        r = requests.post(webhook, json={"content": content[:1900]}, timeout=15)
        if r.status_code >= 400:
            return False, f"Discord 回應 {r.status_code}"
        return True, "ok"
    except Exception as e:
        return False, str(e)[:200]


def send_telegram(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not token or not chat_id:
        return False, "未設定 Telegram token / chat_id"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
            timeout=15,
        )
        if r.status_code >= 400:
            return False, f"Telegram 回應 {r.status_code}"
        return True, "ok"
    except Exception as e:
        return False, str(e)[:200]


def notify_all(settings: dict, text: str) -> dict:
    """依使用者設定推到所有有設定的管道。回傳各管道結果。"""
    results = {}
    if settings.get("discord_webhook"):
        ok, msg = send_discord(settings["discord_webhook"], text)
        results["discord"] = {"ok": ok, "msg": msg}
    if settings.get("telegram_token") and settings.get("telegram_chat_id"):
        ok, msg = send_telegram(settings["telegram_token"], settings["telegram_chat_id"], text)
        results["telegram"] = {"ok": ok, "msg": msg}
    return results
