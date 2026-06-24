"""監看:定時抓指定網址,偵測「開賣 / 有貨」狀態變化,變可購買時推播通知。

注意:用 requests 抓靜態 HTML。對需要 JS 才顯示庫存的網站(如部分票務平台)
可能看不到狀態,這是先天限制。請克制監看頻率,避免被網站封鎖。
"""
import requests
from bs4 import BeautifulSoup

import db
import money
import notify
from crawler.utils import extract_price

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# 預設判斷字眼(使用者可自訂覆蓋)
DEFAULT_AVAILABLE = [
    "立即購買", "加入購物車", "立即購票", "購票", "我要購買", "現在購買", "現貨",
    "buy now", "add to cart", "add-to-cart", "in stock", "available", "instock",  # schema.org InStock
]
DEFAULT_UNAVAILABLE = [
    "售完", "已售完", "已售罄", "完售", "缺貨", "暫無庫存", "補貨中",
    "sold out", "sold-out", "out of stock", "unavailable", "coming soon", "敬請期待",
    "outofstock", "soldout",  # schema.org OutOfStock / SoldOut
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

    name = w["name"] or w["url"]

    # 內容變動模式:對比上次品項清單,有新增/減少就通知(新上架/下架)
    if w.get("mode") == "content":
        from crawler.detail_scraper import items_from_soup
        try:
            resp = requests.get(w["url"], headers=_HEADERS, timeout=20)
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            return {"ok": False, "reason": f"抓取失敗:{e}"[:200]}
        items = items_from_soup(soup, w["url"])
        cur: dict = {}
        for it in items:
            t = (it.get("title") or "").strip()
            if t:
                cur[t] = (it.get("price") or "").strip()
        prev = dict(w.get("snapshot") or [])  # 上次:{標題: 價格}
        on = set(w.get("notify_on") or ["new", "removed", "price"])
        notified = False
        if prev:  # 第一次只建立基準,不通知
            added = [t for t in cur if t not in prev]
            removed = [t for t in prev if t not in cur]
            changed = [(t, prev[t], cur[t]) for t in cur if t in prev and cur[t] and prev[t] != cur[t]]
            lines = []
            if "new" in on and added:
                lines.append(f"➕ 新增 {len(added)} 項:" + "、".join(added[:5]) + ("…" if len(added) > 5 else ""))
            if "removed" in on and removed:
                lines.append(f"➖ 下架 {len(removed)} 項:" + "、".join(removed[:5]) + ("…" if len(removed) > 5 else ""))
            if "price" in on and changed:
                lines.append("💲 改價 %d 項:" % len(changed) + "、".join(f"{t} {a}→{b}" for t, a, b in changed[:5]) + ("…" if len(changed) > 5 else ""))
            if lines:
                settings = db.get_settings(w["user_id"])
                embed = notify.make_embed("🔔 頁面內容變動", f"{name}", w["url"])
                notify.notify_all(settings, f"🔔 TamonRadar 監看:{name}\n" + "\n".join(lines) + f"\n{w['url']}", embed=embed)
                notified = True
        db.set_watch_snapshot(watch_id, [[t, p] for t, p in cur.items()])
        return {"ok": True, "mode": "content", "items": len(cur), "notified": notified}

    try:
        resp = requests.get(w["url"], headers=_HEADERS, timeout=20)
        text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
    except Exception as e:
        return {"ok": False, "reason": f"抓取失敗:{e}"[:200]}

    # 動態頁:庫存狀態常藏在 <script> 的 JSON(schema.org availability / 前端狀態),
    # 所以連同原始 HTML(含 script)一起比對,免瀏覽器也能抓到動態狀態。
    searchable = text + " " + resp.text
    status = _evaluate(searchable, w["available_keywords"], w["unavailable_keywords"])
    prev = w["last_status"]
    name = w["name"] or w["url"]

    # 價格門檻:抓現價(台幣),低於目標就通知
    target = w.get("target_price")
    cur_twd = money.to_twd(extract_price(text)) if target else None
    prev_twd = w.get("last_price_twd")

    db.set_watch_status(watch_id, status, cur_twd)

    settings = db.get_settings(w["user_id"])
    notified = False

    if status == "available" and prev != "available":
        embed = notify.make_embed("🎫 可以買了!", f"「{name}」偵測到可購買。", w["url"], 0x10B981, w.get("image_url", ""))
        notify.notify_all(settings, f"🎫 TamonRadar 監看:「{name}」可能可以買了!\n{w['url']}", embed=embed)
        notified = True

    if target and cur_twd and cur_twd <= target and (prev_twd is None or prev_twd > target):
        embed = notify.make_embed("💰 降到目標價!", f"「{name}」現價 NT${cur_twd}(目標 {target})", w["url"], 0xEF4444)
        notify.notify_all(settings, f"💰 TamonRadar 監看:「{name}」降到 NT${cur_twd}(目標 {target})\n{w['url']}", embed=embed)
        notified = True

    return {"ok": True, "status": status, "price_twd": cur_twd, "previous": prev, "notified": notified}
