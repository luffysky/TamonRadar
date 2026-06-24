"""統一 AI 介面:支援 OpenAI / Gemini / Groq / OpenRouter / Anthropic。

- 除 Anthropic 外,其餘都用 OpenAI 相容 API(同一個 openai SDK,換 base_url + model)。
- 金鑰優先序:使用者自備(BYO)> 後端共用環境變數。
- 預設嘗試順序:openai → gemini → groq → openrouter → anthropic;可用 prefer 指定優先。
"""
import os

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


def _key_for(provider: str, user_keys: dict) -> str:
    user_val = user_keys.get(_USER_KEY_FIELD[provider], "")
    if user_val:
        return user_val
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "")
    return os.environ.get(_OPENAI_COMPATIBLE[provider]["env_key"], "")


def _pick(user_keys: dict, prefer: str) -> str | None:
    prefer = (prefer or os.environ.get("AI_PROVIDER", "")).lower()
    order = ([prefer] if prefer in ORDER else []) + [p for p in ORDER if p != prefer]
    for p in order:
        if _key_for(p, user_keys):
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


def _record(user_id, provider, model, in_tok, out_tok):
    if not user_id:
        return
    try:
        import db
        db.record_ai_cost(user_id, provider, model, int(in_tok or 0), int(out_tok or 0),
                          _cost_usd(model, in_tok or 0, out_tok or 0))
    except Exception:
        pass


def ai_complete(prompt: str, max_tokens: int = 1500,
                user_keys: dict | None = None, prefer: str = "",
                user_id: int | None = None) -> tuple[str | None, str]:
    user_keys = user_keys or {}
    provider = _pick(user_keys, prefer)
    if not provider:
        return None, ""
    key = _key_for(provider, user_keys)

    if provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
        m = client.messages.create(model=model, max_tokens=max_tokens,
                                    messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        u = getattr(m, "usage", None)
        _record(user_id, "anthropic", model, getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0))
        return text, f"anthropic:{model}"

    cfg = _OPENAI_COMPATIBLE[provider]
    model = os.environ.get(cfg["env_model"], cfg["default_model"])
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=cfg["base_url"]) if cfg["base_url"] else OpenAI(api_key=key)
    r = client.chat.completions.create(model=model, max_tokens=max_tokens,
                                       messages=[{"role": "user", "content": prompt}])
    u = getattr(r, "usage", None)
    _record(user_id, provider, model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
    return (r.choices[0].message.content or ""), f"{provider}:{model}"
