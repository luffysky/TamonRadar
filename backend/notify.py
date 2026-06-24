"""推播通知:Discord Webhook 與 Telegram Bot。"""
import os

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


def send_discord_dm(bot_token: str, user_id: str, content: str = "", embed: dict | None = None) -> tuple[bool, str]:
    """用平台共用 Discord bot 私訊使用者(需對方允許 DM / 同伺服器)。"""
    if not bot_token or not user_id:
        return False, "缺 bot token / user id"
    try:
        headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
        ch = requests.post("https://discord.com/api/v10/users/@me/channels",
                           json={"recipient_id": str(user_id)}, headers=headers, timeout=15)
        if ch.status_code >= 400:
            return False, f"開 DM 失敗 {ch.status_code}"
        cid = ch.json().get("id")
        payload: dict = {}
        if content:
            payload["content"] = content[:1900]
        if embed:
            payload["embeds"] = [embed]
        r = requests.post(f"https://discord.com/api/v10/channels/{cid}/messages", json=payload, headers=headers, timeout=15)
        return (r.status_code < 400, "ok" if r.status_code < 400 else f"DM 回應 {r.status_code}")
    except Exception as e:
        return False, str(e)[:200]


def notify_all(settings: dict, text: str, embed: dict | None = None) -> dict:
    """推到使用者管道;沒填自己的就用平台共用 bot(Telegram 用 chat_id、Discord 用 user id DM)。"""
    results = {}
    central_tg = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    central_dc = os.environ.get("DISCORD_BOT_TOKEN", "")

    # Discord 優先序:自己的 webhook → 平台 bot DM(你的 user id)→ 平台共用頻道 webhook(env)
    central_webhook = os.environ.get("DISCORD_WEBHOOK", "")
    if settings.get("discord_webhook"):
        ok, msg = send_discord(settings["discord_webhook"], content=("" if embed else text), embed=embed)
        results["discord"] = {"ok": ok, "msg": msg}
    elif settings.get("discord_user_id") and central_dc:
        ok, msg = send_discord_dm(central_dc, settings["discord_user_id"], content=("" if embed else text), embed=embed)
        results["discord"] = {"ok": ok, "msg": msg}
    elif central_webhook:
        ok, msg = send_discord(central_webhook, content=("" if embed else text), embed=embed)
        results["discord"] = {"ok": ok, "msg": msg}

    # Telegram:有 chat_id 就送;token 優先用自己的,否則用平台共用 bot
    chat_id = settings.get("telegram_chat_id")
    tg_token = settings.get("telegram_token") or central_tg
    if chat_id and tg_token:
        ok, msg = send_telegram(tg_token, chat_id, text)
        results["telegram"] = {"ok": ok, "msg": msg}
    return results
