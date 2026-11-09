"""共用 AI 機器人:Telegram(webhook)與 Discord(interactions)都能跟使用者對話。

回答用後端共用 AI 金鑰 + 網站知識庫。需設定對應的 bot 環境變數。
"""
import hmac
import os

import requests

import ai
import db
import jobs
import ratelimit
from knowledge import KNOWLEDGE


def answer(question: str, actor: str) -> str:
    """actor 是提問來源(telegram:<chat_id> / discord:<user>),用來限流與記錄成本。"""
    question = (question or "").strip()[:2000]
    if not question:
        return "請問我關於 TamonRadar 的問題 🙂"
    if not ai.ai_available():
        return "AI 暫時無法使用(後端尚未設定 AI 金鑰)。"
    prompt = (
        KNOWLEDGE
        + "\n\n你是 TamonRadar 的 AI 助手,請用繁體中文、友善、簡潔地回答使用者的問題。"
        "若問題和 TamonRadar 有關,優先參考上面的網站說明;若是一般性問題(購物、比價、生活、知識等),"
        "也請正常、實用地回答,不要拒答。只有在被要求做違法或有害的事時才婉拒。\n\n問題:" + question
    )
    try:
        text, _ = ai.ai_complete(prompt, max_tokens=800, actor=actor)
    except ratelimit.RateLimited as e:
        return e.message
    return text or "抱歉,我這邊暫時無法回答,請稍後再試。"


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
        telegram_send(chat_id, "嗨!我是 TamonRadar 小幫手 🦊\n直接問我問題;或輸入 /bind 綁定碼 來綁定帳號收通知。")
        return
    if text.startswith("/bind"):
        code = text.replace("/bind", "", 1).strip()
        if not code:
            telegram_send(chat_id, "用法:/bind 你的綁定碼(到網站「設定」產生)")
            return
        _ok, msg = db.consume_bind_code(code, "telegram", str(chat_id))
        telegram_send(chat_id, msg)
        return
    # 需要呼叫 AI 的走工作佇列:webhook 立刻回應,回覆由工作者送出
    uname = (msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name") or str(chat_id))
    update_id = update.get("update_id")
    jobs.enqueue("bot_telegram", config={"chat_id": chat_id, "text": text, "uname": uname},
                 dedupe_key=f"tg:{update_id}" if update_id is not None else None, priority=10, max_attempts=1)


def handle_telegram(update: dict) -> None:
    _handle_telegram(update)


def run_telegram(cfg: dict) -> None:
    ans = answer(cfg["text"], f"telegram:{cfg['chat_id']}")
    db.add_bot_chat_log("telegram", cfg.get("uname", ""), cfg["text"], ans)
    telegram_send(cfg["chat_id"], ans)


def telegram_webhook_secret_ok(secret: str) -> bool:
    """驗證 webhook 路徑上的密鑰;沒設 TELEGRAM_WEBHOOK_SECRET 一律拒絕(fail-closed)。"""
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    return bool(expected) and hmac.compare_digest(secret.encode(), expected.encode())


def telegram_set_webhook(base_url: str) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"ok": False, "error": "未設定 TELEGRAM_BOT_TOKEN"}
    if not base_url.startswith("https://"):
        return {"ok": False, "error": f"webhook 必須是 https,目前 base={base_url};請設 OAUTH_REDIRECT_BASE 為後端 https 網址"}
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not secret:
        return {"ok": False, "error": "未設定 TELEGRAM_WEBHOOK_SECRET,為安全起見拒絕設定 webhook"}
    url = f"{base_url.rstrip('/')}/api/telegram/webhook/{secret}"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": url, "allowed_updates": ["message"], "drop_pending_updates": True},
            timeout=20,
        )
        info = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=15).json()
        res = r.json()
        return {"ok": bool(res.get("ok")), "webhook": url, "setWebhook": res, "info": info.get("result", {})}
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


def enqueue_discord_command(interaction_id: str, app_id: str, token: str, question: str, user: str = "") -> None:
    """Discord 要求 3 秒內回應:先 defer,實際回答由工作者用 followup 編輯。"""
    jobs.enqueue("bot_discord", config={"app_id": app_id, "token": token, "question": question, "user": user},
                 dedupe_key=f"dc:{interaction_id}" if interaction_id else None, priority=10, max_attempts=1)


def run_discord(cfg: dict) -> None:
    ans = answer(cfg["question"], f"discord:{cfg.get('user') or cfg['token'][:12]}")
    db.add_bot_chat_log("discord", cfg.get("user", ""), cfg["question"], ans)
    _discord_followup(cfg["app_id"], cfg["token"], ans)


def discord_register_command() -> dict:
    """註冊 /ask 與 /bind 斜線指令(需 DISCORD_BOT_TOKEN + DISCORD_APP_ID)。"""
    bot = os.environ.get("DISCORD_BOT_TOKEN")
    app_id = os.environ.get("DISCORD_APP_ID")
    if not bot or not app_id:
        return {"ok": False, "error": "未設定 DISCORD_BOT_TOKEN / DISCORD_APP_ID"}
    cmds = [
        {"name": "ask", "description": "問 TamonRadar 助手任何問題",
         "options": [{"type": 3, "name": "question", "description": "你的問題", "required": True}]},
        {"name": "bind", "description": "綁定 TamonRadar 帳號(到網站設定產生綁定碼)",
         "options": [{"type": 3, "name": "code", "description": "網站給的綁定碼", "required": True}]},
    ]
    results = []
    try:
        for cmd in cmds:
            r = requests.post(
                f"https://discord.com/api/v10/applications/{app_id}/commands",
                headers={"Authorization": f"Bot {bot}"}, json=cmd, timeout=20,
            )
            results.append({cmd["name"]: r.status_code})
        return {"ok": True, "registered": results}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def discord_bind(code: str, discord_user_id: str) -> str:
    ok, msg = db.consume_bind_code(code, "discord", discord_user_id)
    return msg
