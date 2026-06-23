"""幣別換算:把抓到的價格字串換算成台幣(TWD)整數,讓不同來源的價格可比較。

匯率用環境變數可調(沒設就用大概值)。這不是即時匯率,只是讓價格雷達能粗略比較。
"""
import os
import re


def _rate(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def rates() -> dict[str, float]:
    return {
        "TWD": 1.0,
        "JPY": _rate("TWD_PER_JPY", 0.22),
        "USD": _rate("TWD_PER_USD", 32.0),
        "CNY": _rate("TWD_PER_CNY", 4.4),
    }


def detect_currency(text: str) -> str:
    t = text.lower()
    if "us$" in t or "usd" in t:
        return "USD"
    if "¥" in text or "円" in text or "jpy" in t or "日圓" in text or "日元" in text:
        return "JPY"
    if "人民幣" in text or "rmb" in t or "cny" in t:
        return "CNY"
    # NT$ / TWD / 元 / 純 $ 在台灣購物情境多半是台幣
    return "TWD"


def to_twd(price_str: str | None) -> int | None:
    """價格字串 → 台幣整數;無法解析回 None。"""
    if not price_str:
        return None
    m = re.search(r"[0-9][0-9,]*", price_str)
    if not m:
        return None
    try:
        amount = int(m.group(0).replace(",", ""))
    except ValueError:
        return None
    if amount <= 0:
        return None
    rate = rates().get(detect_currency(price_str), 1.0)
    return round(amount * rate)


def twd_display(price_str: str | None) -> str:
    """回傳像 'NT$3,500' 的台幣顯示;無法換算回空字串。"""
    twd = to_twd(price_str)
    if twd is None:
        return ""
    return f"NT${twd:,}"
