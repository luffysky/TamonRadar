"""統一 AI 介面:支援 OpenAI(GPT)與 Anthropic(Claude),預設先用 GPT。

金鑰來源優先序:使用者自備(BYO)> 後端共用環境變數。
- 使用者可在「設定」填自己的 OPENAI/ANTHROPIC 金鑰,各付各的。
- 沒填則用後端的 OPENAI_API_KEY / ANTHROPIC_API_KEY。
"""
import os


def _resolve(openai_key: str = "", anthropic_key: str = "", prefer: str = ""):
    """回傳 (provider, openai_key, anthropic_key)。使用者金鑰優先,否則用環境變數。"""
    ok = openai_key or os.environ.get("OPENAI_API_KEY", "")
    ak = anthropic_key or os.environ.get("ANTHROPIC_API_KEY", "")
    pref = (prefer or os.environ.get("AI_PROVIDER", "")).lower()

    if pref == "openai":
        provider = "openai" if ok else ("anthropic" if ak else None)
    elif pref == "anthropic":
        provider = "anthropic" if ak else ("openai" if ok else None)
    else:  # 預設先 GPT
        provider = "openai" if ok else ("anthropic" if ak else None)
    return provider, ok, ak


def ai_available(openai_key: str = "", anthropic_key: str = "", prefer: str = "") -> bool:
    provider, _, _ = _resolve(openai_key, anthropic_key, prefer)
    return provider is not None


def ai_complete(prompt: str, max_tokens: int = 1500,
                openai_key: str = "", anthropic_key: str = "", prefer: str = "") -> tuple[str | None, str]:
    """回傳 (文字, "provider:model")。沒有可用 AI 時回 (None, "")。"""
    provider, ok, ak = _resolve(openai_key, anthropic_key, prefer)

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=ok)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        r = client.chat.completions.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return (r.choices[0].message.content or ""), f"openai:{model}"

    if provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=ak)
        model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
        m = client.messages.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        return text, f"anthropic:{model}"

    return None, ""
