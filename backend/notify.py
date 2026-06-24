"""推播通知:Discord Webhook 與 Telegram Bot。"""
import requests


def send_discord(webhook: str, content: str = "", embed: dict | None = None) -> tuple[bool, str]:
    if not webhook:
        return False, "未設定 Discord webhook"
    payload: dict = {}
    if content:
        payload["content"] = content[:1900]
    if embed:
        payload["embeds"] = [embed]
    if not payload:
        return False, "空訊息"
    try:
        r = requests.post(webhook, json=payload, timeout=15)
        if r.status_code >= 400:
            return False, f"Discord 回應 {r.status_code}"
        return True, "ok"
    except Exception as e:
        return False, str(e)[:200]


def make_embed(title: str, description: str = "", url: str = "", color: int = 0x2F5597, thumbnail: str = "") -> dict:
    embed: dict = {"title": title[:256], "color": color}
    if description:
        embed["description"] = description[:2000]
    if url:
        embed["url"] = url
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    return embed


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


def notify_all(settings: dict, text: str, embed: dict | None = None) -> dict:
    """依使用者設定推到所有有設定的管道。Discord 有 embed 用 embed,Telegram 用純文字。"""
    results = {}
    if settings.get("discord_webhook"):
        ok, msg = send_discord(settings["discord_webhook"], content=("" if embed else text), embed=embed)
        results["discord"] = {"ok": ok, "msg": msg}
    if settings.get("telegram_token") and settings.get("telegram_chat_id"):
        ok, msg = send_telegram(settings["telegram_token"], settings["telegram_chat_id"], text)
        results["telegram"] = {"ok": ok, "msg": msg}
    return results
