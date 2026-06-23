"""統一 AI 介面:支援 OpenAI(GPT)與 Anthropic(Claude),預設先用 GPT。

選擇邏輯:
- AI_PROVIDER=openai / anthropic 可強制指定。
- 沒指定時:有 OPENAI_API_KEY 就用 GPT,否則用 Claude,都沒有就停用。
"""
import os


def _provider() -> str | None:
    pref = os.environ.get("AI_PROVIDER", "").lower()
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if pref == "openai":
        return "openai" if has_openai else ("anthropic" if has_anthropic else None)
    if pref == "anthropic":
        return "anthropic" if has_anthropic else ("openai" if has_openai else None)

    # 預設:先用 GPT
    if has_openai:
        return "openai"
    if has_anthropic:
        return "anthropic"
    return None


def ai_available() -> bool:
    return _provider() is not None


def current_model() -> str:
    p = _provider()
    if p == "openai":
        return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if p == "anthropic":
        return os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    return ""


def ai_complete(prompt: str, max_tokens: int = 1500) -> tuple[str | None, str]:
    """回傳 (文字, "provider:model")。沒有可用 AI 時回 (None, "")。"""
    p = _provider()
    if p == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        r = client.chat.completions.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return (r.choices[0].message.content or ""), f"openai:{model}"

    if p == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
        m = client.messages.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        return text, f"anthropic:{model}"

    return None, ""
