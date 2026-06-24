"""共用 AI 機器人:Telegram(webhook)與 Discord(interactions)都能跟使用者對話。

回答用後端共用 AI 金鑰 + 網站知識庫。需設定對應的 bot 環境變數。
"""
import os
import threading

import requests

import ai
from knowledge import KNOWLEDGE


def answer(question: str) -> str:
    question = (question or "").strip()
    if not question:
        return "請問我關於 TamonRadar 的問題 🙂"
    if not ai.ai_available():
        return "AI 暫時無法使用(後端尚未設定 AI 金鑰)。"
    prompt = (
        KNOWLEDGE
        + "\n\n你是 TamonRadar 的助手,只根據上面的網站說明用繁體中文簡潔回答。"
        "與本站無關就禮貌說明你主要回答 TamonRadar 相關問題。\n\n問題:" + question
    )
    text, _ = ai.ai_complete(prompt, max_tokens=600)
    return text or "抱歉,我無法回答。"


# ---------- Telegram ----------

def telegram_send(chat_id, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
            timeout=20,
        )
    except Exception:
        pass


def _handle_telegram(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message") or {}
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return
    if text.startswith("/start"):
        telegram_send(chat_id, "嗨!我是 TamonRadar 小幫手 🦊\n直接問我任何關於這個網站怎麼用的問題吧。")
        return
    telegram_send(chat_id, answer(text))


def handle_telegram_async(update: dict) -> None:
    threading.Thread(target=_handle_telegram, args=(update,), daemon=True).start()


def telegram_set_webhook(base_url: str) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"ok": False, "error": "未設定 TELEGRAM_BOT_TOKEN"}
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "tamon")
    url = f"{base_url.rstrip('/')}/api/telegram/webhook/{secret}"
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json={"url": url}, timeout=20)
        return {"ok": True, "webhook": url, "telegram": r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ---------- Discord ----------

def verify_discord(signature: str, timestamp: str, body: bytes) -> bool:
    pubkey = (os.environ.get("DISCORD_PUBLIC_KEY") or "").strip()
    if not pubkey:
        print("[discord] ⚠️ 未設定 DISCORD_PUBLIC_KEY,互動端點無法驗證")
        return False
    if not signature or not timestamp:
        return False
    try:
        from nacl.signing import VerifyKey
        VerifyKey(bytes.fromhex(pubkey)).verify(timestamp.encode() + body, bytes.fromhex(signature.strip()))
        return True
    except Exception:
        return False


def _discord_followup(app_id: str, token: str, content: str) -> None:
    try:
        requests.patch(
            f"https://discord.com/api/v10/webhooks/{app_id}/{token}/messages/@original",
            json={"content": content[:1900]},
            timeout=20,
        )
    except Exception:
        pass


def handle_discord_command_async(app_id: str, token: str, question: str) -> None:
    threading.Thread(target=lambda: _discord_followup(app_id, token, answer(question)), daemon=True).start()


def discord_register_command() -> dict:
    """註冊 /ask 斜線指令(需 DISCORD_BOT_TOKEN + DISCORD_APP_ID)。"""
    bot = os.environ.get("DISCORD_BOT_TOKEN")
    app_id = os.environ.get("DISCORD_APP_ID")
    if not bot or not app_id:
        return {"ok": False, "error": "未設定 DISCORD_BOT_TOKEN / DISCORD_APP_ID"}
    cmd = {
        "name": "ask",
        "description": "問 TamonRadar 助手任何問題",
        "options": [{"type": 3, "name": "question", "description": "你的問題", "required": True}],
    }
    try:
        r = requests.post(
            f"https://discord.com/api/v10/applications/{app_id}/commands",
            headers={"Authorization": f"Bot {bot}"},
            json=cmd, timeout=20,
        )
        return {"ok": r.status_code < 300, "discord": r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
