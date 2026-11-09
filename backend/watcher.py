"""監看:定時抓指定網址,偵測「開賣 / 有貨」狀態變化,變可購買時推播通知。

注意:用 requests 抓靜態 HTML。對需要 JS 才顯示庫存的網站(如部分票務平台)
可能看不到狀態,這是先天限制。請克制監看頻率,避免被網站封鎖。
"""
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import PreformattedString

import db
import money
import notify
import quota
from crawler.detail_scraper import _structured_price
from crawler.utils import extract_price, looks_like_block_page
from safe_fetch import ResponseTooLarge, UnsafeURLError, safe_get


# CTA 按鈕常見字眼(結帳/預購/到貨通知…),比庫存關鍵字更廣
CTA_KEYWORDS = [
    "立即購買", "加入購物車", "我要購買", "現在購買", "直接購買", "立即結帳", "結帳", "去買",
    "立即購票", "購票", "馬上搶", "立即預購", "預購", "預訂", "訂購", "下單",
    "到貨通知", "補貨通知", "缺貨通知", "貨到通知", "到貨提醒",
    "buy now", "add to cart", "add-to-cart", "checkout", "pre-order", "preorder",
    "order now", "notify me", "purchase",
]


_CART_HINTS = ("/cart", "/checkout", "add-to-cart", "add_to_cart", "?add-to-cart", "addtocart", "/buy", "/dp/", "/products/", "/product/")
_ATTR_HINTS = ("add-to-cart", "addtocart", "add_to_cart", "buy", "checkout", "purchase", "btn-cart", "product-form", "add-cart", "cta")


def _find_cta(soup, base_url: str, avail_kws: list | None = None) -> tuple[str, str]:
    """動態偵測對方頁面的「行動路徑」(購買/結帳)而非寫死字眼。

    依結構訊號評分:表單 action(/cart/add)、連結 href(/cart、/checkout、?add-to-cart=)、
    元素 class/id(add-to-cart、buy、checkout)。文字關鍵字只當最弱的輔助。
    """
    from urllib.parse import urlparse
    home = urlparse(base_url).path.rstrip("/")

    def ok(full: str) -> bool:
        p = urlparse(full).path.rstrip("/")
        return p not in ("", "/", home)

    best = None  # (score, text, url)

    # 1) 加入購物車 / 結帳 表單(Shopify / WooCommerce 最可靠)
    for f in soup.find_all("form", action=True):
        act = (f["action"] or "").lower()
        if any(h in act for h in ("cart", "checkout", "add")):
            full = urljoin(base_url, f["action"])
            if ok(full):
                best = (4, "前往購買", full)
                break

    # 2) 連結:看 href / class / id 的結構訊號
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(base_url, href)
        if not ok(full):
            continue
        low = full.lower()
        attrs = (" ".join(a.get("class", [])) + " " + (a.get("id") or "") + " " + (a.get("data-action") or "")).lower()
        t = a.get_text(" ", strip=True)
        score = 0
        if any(h in low for h in _CART_HINTS):
            score = 3
        if any(h in attrs for h in _ATTR_HINTS):
            score = max(score, 3)
        if score == 0 and t and any(k in t.lower() for k in CTA_KEYWORDS + [k.lower() for k in (avail_kws or [])]):
            score = 1  # 純文字最弱
        if score and (best is None or score > best[0]):
            best = (score, (t[:60] or "前往購買"), full)

    return (best[1], best[2]) if best else ("", "")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# 預設判斷字眼(使用者可自訂覆蓋);只比對使用者看得到的文字
DEFAULT_AVAILABLE = [
    "立即購買", "加入購物車", "立即購票", "購票", "我要購買", "現在購買", "現貨", "立即預購",
    "buy now", "add to cart", "add-to-cart", "in stock", "instock", "available now", "order now", "pre-order",
]
DEFAULT_UNAVAILABLE = [
    "售完", "已售完", "已售罄", "完售", "缺貨", "暫無庫存", "補貨中", "敬請期待", "尚未開賣",
    "sold out", "sold-out", "soldout", "out of stock", "out-of-stock", "outofstock",
    "unavailable", "not available", "no longer available", "coming soon",
]

# schema.org ItemAvailability(含常見的小寫/底線變體,比對前會先正規化)
_SCHEMA_AVAILABLE = {
    "instock", "preorder", "presale", "limitedavailability", "onlineonly",
    "instoreonly", "backorder", "madetoorder", "available",
}
_SCHEMA_UNAVAILABLE = {"outofstock", "soldout", "discontinued", "oos", "unavailable", "notavailable"}

_PREFIX_Q = r'\\?"'
_JSON_IN_STOCK = re.compile(
    _PREFIX_Q + r'(?:available|is_?available|in_?stock|is_?in_?stock|has_?stock)' + _PREFIX_Q + r"\s*:\s*(true|false)\b", re.I)
_JSON_SOLD_OUT = re.compile(
    _PREFIX_Q + r'(?:sold_?out|is_?sold_?out|out_?of_?stock|is_?out_?of_?stock)' + _PREFIX_Q + r"\s*:\s*(true|false)\b", re.I)
_JSON_STATUS = re.compile(
    _PREFIX_Q + r'(?:availability|availability_?status|stock_?status)' + _PREFIX_Q + r'\s*:\s*' + _PREFIX_Q + r'([^"\\]{1,60})' + _PREFIX_Q, re.I)

_MAX_SCRIPT_SCAN = 2_000_000
_NON_VISIBLE_TAGS = {"script", "style", "noscript", "template", "head"}
_RELATED_KEYS = {"isrelatedto", "issimilarto", "isaccessoryorsparepartfor", "isconsumablefor", "review", "reviews"}
_PRODUCT_TYPES = {"product", "productgroup", "individualproduct", "productmodel", "vehicle"}

# 反爬/驗證頁特徵:只在頁面內容很短時才採信,避免一般商品頁提到這些字被誤判
_BLOCK_PHRASES = (
    "just a moment", "attention required", "access denied", "verify you are human", "are you a robot",
    "checking your browser", "enable javascript and cookies", "request blocked", "請證明您不是機器人", "異常流量",
)
_BLOCK_PAGE_MAX_TEXT = 1500


def _schema_status(value) -> str | None:
    """把 schema.org / JSON 的庫存值正規化成 available / unavailable。"""
    if not isinstance(value, str):
        return None
    token = re.sub(r"[\s_-]", "", value.strip().rstrip("/").rsplit("/", 1)[-1]).lower()
    if token in _SCHEMA_AVAILABLE:
        return "available"
    if token in _SCHEMA_UNAVAILABLE:
        return "unavailable"
    return None


def _node_types(node: dict) -> set[str]:
    raw = node.get("@type") or []
    return {str(t).lower() for t in (raw if isinstance(raw, list) else [raw])}


def _iter_products(data):
    """走訪 JSON-LD,取出最外層的 Product 節點(不往商品內部找,避免算到相關商品)。"""
    if isinstance(data, list):
        for item in data:
            yield from _iter_products(item)
    elif isinstance(data, dict):
        if _node_types(data) & _PRODUCT_TYPES:
            yield data
            return
        for value in data.values():
            yield from _iter_products(value)


def _offer_statuses(node) -> set[str]:
    """收集節點內所有 availability 的判定結果,略過相關商品與評論。"""
    found: set[str] = set()
    if isinstance(node, list):
        for item in node:
            found |= _offer_statuses(item)
    elif isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in _RELATED_KEYS:
                continue
            if str(key).lower() == "availability":
                status = _schema_status(value)
                if status:
                    found.add(status)
            elif isinstance(value, (dict, list)):
                found |= _offer_statuses(value)
    return found


def _unanimous(statuses) -> str | None:
    distinct = set(statuses)
    return distinct.pop() if len(distinct) == 1 else None


def _jsonld_availability(soup) -> str | None:
    """JSON-LD。單一商品有任一規格可買就算可買;頁面上多個商品狀態不一致時不下結論。"""
    per_product: list[str] = []
    bare_offers: set[str] = set()
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw, strict=False)
        except ValueError:
            continue
        products = list(_iter_products(data))
        for product in products:
            statuses = _offer_statuses(product)
            if "available" in statuses:
                per_product.append("available")
            elif "unavailable" in statuses:
                per_product.append("unavailable")
        if not products:
            bare_offers |= _offer_statuses(data)
    return _unanimous(per_product) if per_product else _unanimous(bare_offers)


def _microdata_availability(soup) -> str | None:
    statuses = []
    for el in soup.find_all(attrs={"itemprop": re.compile("^availability$", re.I)}):
        status = _schema_status(el.get("href") or el.get("content") or el.get_text(strip=True))
        if status:
            statuses.append(status)
    for prop in ("product:availability", "og:availability"):
        el = soup.find("meta", attrs={"property": prop})
        if el and el.get("content"):
            status = _schema_status(el["content"])
            if status:
                statuses.append(status)
    return _unanimous(statuses)


def _script_json_availability(soup) -> str | None:
    """常見的內嵌 JSON(如 Shopify 的 "available":false)。訊號互相矛盾時不下結論,交給頁面文字判斷。"""
    remaining = _MAX_SCRIPT_SCAN
    statuses: list[str] = []
    for script in soup.find_all("script"):
        if "ld+json" in (script.get("type") or "").lower():
            continue
        text = (script.string or "")[:remaining]
        if not text:
            continue
        remaining -= len(text)
        statuses += ["available" if m.lower() == "true" else "unavailable" for m in _JSON_IN_STOCK.findall(text)]
        statuses += ["unavailable" if m.lower() == "true" else "available" for m in _JSON_SOLD_OUT.findall(text)]
        statuses += [st for st in (_schema_status(m) for m in _JSON_STATUS.findall(text)) if st]
        if remaining <= 0:
            break
    return _unanimous(statuses)


def _structured_availability(soup) -> str | None:
    return _jsonld_availability(soup) or _microdata_availability(soup) or _script_json_availability(soup)


def _visible_text(soup) -> str:
    """只取使用者看得到的文字:排除 script/style、隱藏元素與註解。"""
    hidden: dict[int, bool] = {}

    def is_hidden(tag) -> bool:
        path = []
        result = False
        while tag is not None:
            if id(tag) in hidden:
                result = hidden[id(tag)]
                break
            style = (tag.get("style") or "").replace(" ", "").lower() if tag.attrs else ""
            if (tag.name in _NON_VISIBLE_TAGS or tag.has_attr("hidden")
                    or "display:none" in style or "visibility:hidden" in style):
                result = True
                path.append(tag)
                break
            path.append(tag)
            tag = tag.parent
        for t in path:
            hidden[id(t)] = result
        return result

    parts = [str(node) for node in soup.find_all(string=True)
             if not isinstance(node, PreformattedString) and not is_hidden(node.parent)]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _keyword_found(keyword: str, text: str) -> bool:
    kw = keyword.strip().lower()
    if not kw:
        return False
    if kw.isascii():  # 英文要整字比對,否則 unavailable 會命中 available
        pattern = r"(?<![a-z0-9])" + re.escape(kw).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return kw in text


def _evaluate(text: str, avail_kws: list[str], unavail_kws: list[str]) -> str:
    """關鍵字判斷:缺貨字眼優先(頁面同時有「售完」和「加入購物車」時視為售完)。"""
    t = text.lower()
    if any(_keyword_found(k, t) for k in (unavail_kws or DEFAULT_UNAVAILABLE)):
        return "unavailable"
    if any(_keyword_found(k, t) for k in (avail_kws or DEFAULT_AVAILABLE)):
        return "available"
    return "unknown"


def detect_availability(soup, avail_kws: list[str] | None = None, unavail_kws: list[str] | None = None) -> str:
    """回傳 available / unavailable / unknown:結構化資料優先,其次才看頁面文字。"""
    return _structured_availability(soup) or _evaluate(_visible_text(soup), avail_kws or [], unavail_kws or [])


@dataclass
class Page:
    html: str
    soup: BeautifulSoup
    text: str


def _fetch_page(url: str) -> tuple[Page | None, str]:
    """抓頁面。失敗(網路錯誤、4xx/5xx、被擋)回 (None, 錯誤原因),絕不可當成庫存狀態變化。"""
    try:
        resp = safe_get(url, headers=_HEADERS, timeout=20)
    except (UnsafeURLError, ResponseTooLarge) as e:
        return None, str(e)
    except Exception as e:
        return None, f"抓取失敗:{e}"[:300]
    if resp.status_code >= 300:
        return None, f"網站回應 HTTP {resp.status_code}"
    html = resp.text or ""
    if not html.strip():
        return None, "網站回應內容是空的"
    soup = BeautifulSoup(html, "lxml")
    text = _visible_text(soup)
    if len(text) < _BLOCK_PAGE_MAX_TEXT:
        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        lowered = f"{title} {text.lower()}"
        if any(p in lowered for p in _BLOCK_PHRASES) or looks_like_block_page(html):
            return None, "被網站的防爬機制擋下(驗證頁),這次無法判斷"
    return Page(html=html, soup=soup, text=text), ""


def _page_price_twd(page: Page) -> int | None:
    """結構化價格優先,整頁文字猜測只當備援。"""
    return money.to_twd(_structured_price(page.soup) or extract_price(page.text))


def check_watch(watch_id: int) -> dict:
    """單一監看全包:同時偵測 補貨 / 新增 / 下架 / 改價,依 notify_on 勾選通知。"""
    try:
        return _check_watch(watch_id)
    except Exception as e:
        reason = f"檢查失敗:{e}"[:300]
        db.set_watch_error(watch_id, reason)
        return {"ok": False, "status": "error", "reason": reason}


def _check_watch(watch_id: int) -> dict:
    w = db.get_watch(watch_id)
    if not w or not w["enabled"]:
        return {"ok": False, "reason": "停用或不存在"}

    name = w["name"] or w["url"]
    from crawler.detail_scraper import items_from_soup

    page, error = _fetch_page(w["url"])
    if page is None:
        # 只記錯誤,不動 last_status:補貨判斷才能跨過這次失敗,接回上一次的已知狀態
        db.set_watch_error(watch_id, error)
        return {"ok": False, "status": "error", "reason": error}
    soup = page.soup

    on = set(w.get("notify_on") or ["new", "removed", "price", "restock"])
    lines: list[str] = []

    # 1) 庫存狀態(補貨)— 只有明確從「售完」變「可買」才通知,unknown 不算
    status = detect_availability(soup, w["available_keywords"], w["unavailable_keywords"])
    prev_status = w["last_status"]
    if "restock" in on and status == "available" and prev_status == "unavailable":
        lines.append(f"🎫 補貨/可購買了(原本:{prev_status})")

    # 2) 目標價
    target = w.get("target_price")
    cur_twd = _page_price_twd(page) if target else None
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
    db.set_watch_cta(watch_id, cta_t, cta_u)  # 找不到就清空(避免留下舊的壞連結)

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


# ---------- 收藏的目標價 ----------

FAVORITE_RECHECK_MINUTES = 60   # 同一個收藏最短多久重抓一次
FAVORITE_BATCH_LIMIT = 200      # 每輪最多檢查幾個,避免一次打太多外站


def check_favorite(fav: dict) -> dict:
    """抓收藏商品的現價;低於目標價且上次還沒低於時才通知(避免每輪重複推播)。"""
    page, error = _fetch_page(fav["url"])
    if page is None:
        db.set_favorite_check(fav["id"], error=error)
        return {"ok": False, "reason": error}
    twd = _page_price_twd(page)
    if twd is None:
        db.set_favorite_check(fav["id"], error="這個頁面找不到價格")
        return {"ok": False, "reason": "找不到價格"}

    target = fav.get("target_twd")
    prev = fav.get("last_price_twd")
    db.set_favorite_check(fav["id"], price_twd=twd)
    if not target or twd > target or (prev is not None and prev <= target):
        return {"ok": True, "price_twd": twd, "notified": False}

    uid = fav["user_id"]
    title = fav.get("title") or fav["url"]
    body = f"🎯 {title} 降到 NT${twd}(目標 {target})"
    db.add_notification(uid, "🎯 目標價通知", body, fav["url"])
    settings = db.get_settings(uid)
    if notify.has_channel(settings):
        notify.notify_all(settings, f"TamonRadar 目標價通知\n{body}\n{fav['url']}")
    return {"ok": True, "price_twd": twd, "notified": True}


def check_due_favorites(pause_seconds: float = 1.0) -> int:
    """排程呼叫:檢查到期的目標價收藏(受每人上限與每輪上限約束)。回傳實際檢查數。"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=FAVORITE_RECHECK_MINUTES)
    caps: dict[int, int] = {}
    used: dict[int, int] = {}
    checked = 0
    for fav in db.list_due_favorites(cutoff):
        if checked >= FAVORITE_BATCH_LIMIT:
            break
        uid = fav["user_id"]
        if uid not in caps:
            caps[uid] = quota.caps_for_id(uid).favorite_targets
        if used.get(uid, 0) >= caps[uid]:
            continue
        used[uid] = used.get(uid, 0) + 1
        try:
            check_favorite(fav)
        except Exception as e:
            db.set_favorite_check(fav["id"], error=f"檢查失敗:{e}"[:300])
        checked += 1
        time.sleep(pause_seconds)
    return checked
