"""監看:定時抓指定網址,偵測「開賣 / 有貨」狀態變化,變可購買時推播通知。

注意:用 requests 抓靜態 HTML。對需要 JS 才顯示庫存的網站(如部分票務平台)
可能看不到狀態,這是先天限制。請克制監看頻率,避免被網站封鎖。
"""
import requests
from bs4 import BeautifulSoup

import db
import notify

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# 預設判斷字眼(使用者可自訂覆蓋)
DEFAULT_AVAILABLE = [
    "立即購買", "加入購物車", "立即購票", "購票", "我要購買", "現在購買",
    "buy now", "add to cart", "add-to-cart", "in stock", "available",
]
DEFAULT_UNAVAILABLE = [
    "售完", "已售完", "已售罄", "完售", "缺貨", "暫無庫存", "補貨中",
    "sold out", "sold-out", "out of stock", "unavailable", "coming soon", "敬請期待",
]


def _evaluate(text: str, avail_kws: list[str], unavail_kws: list[str]) -> str:
    t = text.lower()
    avail = avail_kws or DEFAULT_AVAILABLE
    unavail = unavail_kws or DEFAULT_UNAVAILABLE
    has_unavail = any(k.lower() in t for k in unavail)
    has_avail = any(k.lower() in t for k in avail)
    if has_unavail and not has_avail:
        return "unavailable"
    if has_avail:
        return "available"
    return "unknown"


def check_watch(watch_id: int) -> dict:
    """檢查一個監看項目;狀態從非 available 變成 available 時推播。回傳結果摘要。"""
    w = db.get_watch(watch_id)
    if not w or not w["enabled"]:
        return {"ok": False, "reason": "停用或不存在"}

    try:
        resp = requests.get(w["url"], headers=_HEADERS, timeout=20)
        text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
    except Exception as e:
        return {"ok": False, "reason": f"抓取失敗:{e}"[:200]}

    status = _evaluate(text, w["available_keywords"], w["unavailable_keywords"])
    prev = w["last_status"]
    db.set_watch_status(watch_id, status)

    notified = False
    if status == "available" and prev != "available":
        settings = db.get_settings(w["user_id"])
        name = w["name"] or w["url"]
        msg = f"🎫 TamonRadar 監看通知\n「{name}」可能可以買了!\n{w['url']}"
        notify.notify_all(settings, msg)
        notified = True

    return {"ok": True, "status": status, "previous": prev, "notified": notified}
