"""統一 AI 介面:支援 OpenAI / Gemini / Groq / OpenRouter / Anthropic。

- 除 Anthropic 外,其餘都用 OpenAI 相容 API(同一個 openai SDK,換 base_url + model)。
- 金鑰優先序:使用者自備(BYO)> 後端共用環境變數。
- 預設嘗試順序:openai → gemini → groq → openrouter → anthropic;可用 prefer 指定優先。
"""
import os

import quota

ORDER = ["openai", "gemini", "groq", "openrouter", "anthropic"]

# OpenAI 相容端點(anthropic 另外處理)
_OPENAI_COMPATIBLE = {
    "openai": {"base_url": None, "env_key": "OPENAI_API_KEY", "env_model": "OPENAI_MODEL", "default_model": "gpt-4o-mini"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "env_key": "GEMINI_API_KEY", "env_model": "GEMINI_MODEL", "default_model": "gemini-2.0-flash"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "env_key": "GROQ_API_KEY", "env_model": "GROQ_MODEL", "default_model": "llama-3.3-70b-versatile"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "env_key": "OPENROUTER_API_KEY", "env_model": "OPENROUTER_MODEL", "default_model": "openai/gpt-4o-mini"},
}
_USER_KEY_FIELD = {
    "openai": "openai_key", "gemini": "gemini_key", "groq": "groq_key",
    "openrouter": "openrouter_key", "anthropic": "anthropic_key",
}


def _db(provider: str, field: str) -> str:
    """從後台設定讀(key 會解密);失敗或沒設回空字串。"""
    try:
        import db
        return db.ai_db_setting(provider, field)
    except Exception:
        return ""


def _enabled(provider: str) -> bool:
    """後台明確設為停用(enabled=0)才視為停用;預設啟用。"""
    return _db(provider, "enabled") != "0"


def _env_key(provider: str) -> str:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "")
    return os.environ.get(_OPENAI_COMPATIBLE[provider]["env_key"], "")


def _key_for(provider: str, user_keys: dict) -> str:
    # 優先序:使用者自備 > 後台設定(DB)> 環境變數
    user_val = user_keys.get(_USER_KEY_FIELD[provider], "")
    if user_val:
        return user_val
    db_val = _db(provider, "key")
    if db_val:
        return db_val
    return _env_key(provider)


def _model_for(provider: str) -> str:
    """模型:後台設定 > 環境變數 > 預設。"""
    db_model = _db(provider, "model")
    if db_model:
        return db_model
    if provider == "anthropic":
        return os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    cfg = _OPENAI_COMPATIBLE[provider]
    return os.environ.get(cfg["env_model"], cfg["default_model"])


def _default_provider() -> str:
    try:
        import db
        return (db.ai_db_default_provider() or os.environ.get("AI_PROVIDER", "")).lower()
    except Exception:
        return os.environ.get("AI_PROVIDER", "").lower()


def _pick(user_keys: dict, prefer: str) -> str | None:
    prefer = (prefer or _default_provider()).lower()
    order = ([prefer] if prefer in ORDER else []) + [p for p in ORDER if p != prefer]
    for p in order:
        # 使用者自備金鑰不受後台停用限制;否則需該 provider 未被停用
        if user_keys.get(_USER_KEY_FIELD[p], ""):
            return p
        if _enabled(p) and _key_for(p, user_keys):
            return p
    return None


def ai_available(user_keys: dict | None = None, prefer: str = "") -> bool:
    return _pick(user_keys or {}, prefer) is not None


# 各模型每 1M tokens 價格(美元,輸入/輸出);未列出的以 0 計
_PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gemini-2.0-flash": (0.10, 0.40),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-3-5-haiku": (0.80, 4.0),
}


def _cost_usd(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = _PRICES.get(model, (0.0, 0.0))
    return round(in_tok / 1_000_000 * pin + out_tok / 1_000_000 * pout, 6)


def _record(user_id, provider, model, in_tok, out_tok, actor=""):
    if not user_id and not actor:
        return
    try:
        import db
        db.record_ai_cost(user_id, provider, model, int(in_tok or 0), int(out_tok or 0),
                          _cost_usd(model, in_tok or 0, out_tok or 0), actor=actor)
    except Exception:
        pass


# 每次呼叫模型的硬上限(不論從哪個入口進來)
MAX_PROMPT_CHARS = int(os.environ.get("AI_MAX_PROMPT_CHARS", "60000"))
MAX_OUTPUT_TOKENS = 4000
_IMAGE_COST_USD = 0.04  # 圖片生成以單張估算


def ai_complete(prompt: str, max_tokens: int = 1500,
                user_keys: dict | None = None, prefer: str = "",
                user_id: int | None = None, actor: str = "") -> tuple[str | None, str]:
    """所有文字 AI 呼叫的唯一入口。user_id=登入使用者;actor=機器人來源(如 telegram:123)。

    額度在這裡統一檢查(超過丟 quota.QuotaExceeded),呼叫端不用也不該自己扣額度。
    """
    user_keys = user_keys or {}
    provider = _pick(user_keys, prefer)
    if not provider:
        return None, ""
    quota.gate_ai(user_id, actor)
    prompt = prompt[:MAX_PROMPT_CHARS]
    max_tokens = min(max_tokens, MAX_OUTPUT_TOKENS)
    key = _key_for(provider, user_keys)

    if provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        model = _model_for("anthropic")
        m = client.messages.create(model=model, max_tokens=max_tokens,
                                    messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        u = getattr(m, "usage", None)
        _record(user_id, "anthropic", model, getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0), actor)
        return text, f"anthropic:{model}"

    cfg = _OPENAI_COMPATIBLE[provider]
    model = _model_for(provider)
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=cfg["base_url"]) if cfg["base_url"] else OpenAI(api_key=key)
    r = client.chat.completions.create(model=model, max_tokens=max_tokens,
                                       messages=[{"role": "user", "content": prompt}])
    u = getattr(r, "usage", None)
    _record(user_id, provider, model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0), actor)
    return (r.choices[0].message.content or ""), f"{provider}:{model}"


def generate_image(prompt: str, user_keys: dict | None = None, user_id: int | None = None) -> bytes | None:
    """用 OpenAI 產生封面圖,回傳 PNG bytes;沒 key 或失敗回 None。額度超過丟 quota.QuotaExceeded。"""
    key = (user_keys or {}).get("openai_key", "") or _db("openai", "key") or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    quota.gate_image(user_id)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        try:
            r = client.images.generate(model="gpt-image-1", prompt=prompt[:900], size="1024x1024", n=1)
        except Exception:
            r = client.images.generate(model="dall-e-3", prompt=prompt[:900], size="1024x1024", n=1)
        d = r.data[0]
        try:
            import db
            db.record_ai_cost(user_id, "openai", "image", 0, 0, _IMAGE_COST_USD)
        except Exception:
            pass
        import base64
        if getattr(d, "b64_json", None):
            return base64.b64decode(d.b64_json)
        if getattr(d, "url", None):
            import requests as _rq
            resp = _rq.get(d.url, timeout=30)
            return resp.content if resp.status_code == 200 else None
    except Exception:
        return None
    return None


def test_provider(provider: str, key: str = "") -> dict:
    """測試某 provider 的金鑰是否可用。key 留空則用現有設定(DB/env)。"""
    if provider not in ORDER:
        return {"ok": False, "error": "未知的 provider"}
    key = (key or "").strip() or _key_for(provider, {})
    if not key:
        return {"ok": False, "error": "尚未設定金鑰"}
    model = _model_for(provider)
    try:
        if provider == "anthropic":
            from anthropic import Anthropic
            Anthropic(api_key=key).messages.create(model=model, max_tokens=5,
                                                    messages=[{"role": "user", "content": "ping"}])
        else:
            cfg = _OPENAI_COMPATIBLE[provider]
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=cfg["base_url"]) if cfg["base_url"] else OpenAI(api_key=key)
            client.chat.completions.create(model=model, max_tokens=5,
                                           messages=[{"role": "user", "content": "ping"}])
        return {"ok": True, "model": model}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "model": model}
