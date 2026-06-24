"""監看:定時抓指定網址,偵測「開賣 / 有貨」狀態變化,變可購買時推播通知。

注意:用 requests 抓靜態 HTML。對需要 JS 才顯示庫存的網站(如部分票務平台)
可能看不到狀態,這是先天限制。請克制監看頻率,避免被網站封鎖。
"""
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import db
import money
import notify
from crawler.utils import extract_price


# CTA 按鈕常見字眼(結帳/預購/到貨通知…),比庫存關鍵字更廣
CTA_KEYWORDS = [
    "立即購買", "加入購物車", "我要購買", "現在購買", "直接購買", "立即結帳", "結帳", "去買",
    "立即購票", "購票", "馬上搶", "立即預購", "預購", "預訂", "訂購", "下單",
    "到貨通知", "補貨通知", "缺貨通知", "貨到通知", "到貨提醒",
    "buy now", "add to cart", "add-to-cart", "checkout", "pre-order", "preorder",
    "order now", "notify me", "purchase",
]


def _find_cta(soup, base_url: str, avail_kws: list) -> tuple[str, str]:
    """找對方頁面的 CTA 連結(立即購買/加入購物車/結帳/預購/到貨通知…),回傳 (文字, 連結)。"""
    kws = CTA_KEYWORDS + [k.lower() for k in (avail_kws or [])]
    # 優先找帶 href 的連結;表單 action 也算
    for a in soup.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        if t and any(k in t.lower() for k in kws):
            return t[:60], urljoin(base_url, a["href"])
    for btn in soup.find_all("button"):
        t = btn.get_text(" ", strip=True)
        if t and any(k in t.lower() for k in kws):
            # 按鈕沒連結 → 退回商品頁本身(至少帶到該頁)
            form = btn.find_parent("form")
            if form and form.get("action"):
                return t[:60], urljoin(base_url, form["action"])
            return t[:60], base_url
    return "", ""

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
    """單一監看全包:同時偵測 補貨 / 新增 / 下架 / 改價,依 notify_on 勾選通知。"""
    w = db.get_watch(watch_id)
    if not w or not w["enabled"]:
        return {"ok": False, "reason": "停用或不存在"}

    name = w["name"] or w["url"]
    from crawler.detail_scraper import items_from_soup
    try:
        resp = requests.get(w["url"], headers=_HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
    except Exception as e:
        return {"ok": False, "reason": f"抓取失敗:{e}"[:200]}

    on = set(w.get("notify_on") or ["new", "removed", "price", "restock"])
    lines: list[str] = []

    # 1) 庫存狀態(補貨)— 連同 script JSON 一起比對,支援動態頁
    status = _evaluate(text + " " + resp.text, w["available_keywords"], w["unavailable_keywords"])
    prev_status = w["last_status"]
    if "restock" in on and status == "available" and prev_status not in ("available", "unknown"):
        lines.append(f"🎫 補貨/可購買了(原本:{prev_status})")

    # 2) 目標價
    target = w.get("target_price")
    cur_twd = money.to_twd(extract_price(text)) if target else None
    prev_twd = w.get("last_price_twd")
    if target and cur_twd and cur_twd <= target and (prev_twd is None or prev_twd > target):
        lines.append(f"💰 降到目標價 NT${cur_twd}(目標 {target})")

    # 3) 內容變動(新增 / 下架 / 改價)— 抓得到品項才比對
    items = items_from_soup(soup, w["url"])
    cur = {(it.get("title") or "").strip(): (it.get("price") or "").strip() for it in items if (it.get("title") or "").strip()}
    prev_items = dict(w.get("snapshot") or [])
    if cur and prev_items:
        added = [t for t in cur if t not in prev_items]
        removed = [t for t in prev_items if t not in cur]
        changed = [(t, prev_items[t], cur[t]) for t in cur if t in prev_items and cur[t] and prev_items[t] != cur[t]]
        if "new" in on and added:
            lines.append(f"➕ 新增 {len(added)} 項:" + "、".join(added[:5]) + ("…" if len(added) > 5 else ""))
        if "removed" in on and removed:
            lines.append(f"➖ 下架 {len(removed)} 項:" + "、".join(removed[:5]) + ("…" if len(removed) > 5 else ""))
        if "price" in on and changed:
            lines.append("💲 改價 %d 項:" % len(changed) + "、".join(f"{t} {a}→{b}" for t, a, b in changed[:5]) + ("…" if len(changed) > 5 else ""))

    # CTA:抓對方頁面的「立即購買/加入購物車」連結存起來
    cta_t, cta_u = _find_cta(soup, w["url"], w["available_keywords"])
    if cta_u:
        db.set_watch_cta(watch_id, cta_t, cta_u)

    # 列表頁(抓到多個品項、頁面層級無單一庫存狀態)→ 顯示「監看內容中」而非「尚未判斷」
    if status == "unknown" and len(cur) >= 2:
        status = "watching"

    # 更新狀態 / 快照
    db.set_watch_status(watch_id, status, cur_twd)
    if cur:
        db.set_watch_snapshot(watch_id, [[t, p] for t, p in cur.items()])

    notified = False
    if lines:
        settings = db.get_settings(w["user_id"])
        link = cta_u or w.get("cta_url") or w["url"]
        body = "\n".join(lines)
        embed = notify.make_embed(f"🔔 監看更新:{name}", body, link)
        notify.notify_all(settings, f"🔔 TamonRadar 監看:{name}\n{body}\n前往:{link}", embed=embed)
        db.add_notification(w["user_id"], f"🔔 監看更新:{name}", body, link)
        notified = True

    return {"ok": True, "status": status, "items": len(cur), "notified": notified}
