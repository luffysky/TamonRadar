import concurrent.futures
import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .utils import clean_text, extract_price, classify_item, sleep_random, looks_like_block_page, is_listing_url, get_domain
from .characters import detect_character

_LIGHT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def _light_fetch_one(url: str) -> dict:
    """用 requests(免瀏覽器)抓單一商品頁的 og:image 與結構化價格。"""
    from . import robots
    if not robots.allowed(url):
        return {}
    try:
        r = requests.get(url, headers=_LIGHT_HEADERS, timeout=8)
        if r.status_code >= 400 or not r.text:
            return {}
        soup = BeautifulSoup(r.text, "lxml")
        out: dict = {}
        og = (soup.find("meta", property="og:image")
              or soup.find("meta", attrs={"name": "og:image"})
              or soup.find("meta", property="twitter:image")
              or soup.find("meta", attrs={"name": "twitter:image"}))
        if og and og.get("content"):
            out["image_url"] = urljoin(url, og["content"].strip())
        # 價格只取可靠的結構化資料(不從整頁文字猜,避免亂價)
        price = _structured_price(soup)
        if price:
            out["price"] = price
        return out
    except Exception:
        return {}


_JSON_NAME_KEYS = {"name", "title", "symbolname", "longname", "shortname", "label", "productname"}
_JSON_PRICE_KEYS = {"price", "last", "lastprice", "regularmarketprice", "close", "value", "amount"}


def _balanced_json(text: str, start: int) -> str | None:
    """從 start(應是 '{')開始取出字串感知的平衡 JSON 物件。"""
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    q = ""
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == q:
                in_str = False
        else:
            if c in "\"'":
                in_str = True
                q = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def _json_price_rows(o, rows: list, depth: int = 0) -> None:
    """遞迴找「有名稱+價格」的物件(供內嵌 JSON / API 回應共用)。"""
    if depth > 12 or len(rows) > 400:
        return
    if isinstance(o, dict):
        low = {k.lower(): k for k in o.keys()}
        nk = next((low[k] for k in _JSON_NAME_KEYS if k in low), None)
        pk = next((low[k] for k in _JSON_PRICE_KEYS if k in low), None)
        if nk and pk:
            name, price = o.get(nk), o.get(pk)
            if isinstance(name, str) and name.strip() and isinstance(price, (int, float, str)) and any(ch.isdigit() for ch in str(price)):
                rows.append((name.strip(), str(price)))
        for v in o.values():
            _json_price_rows(v, rows, depth + 1)
    elif isinstance(o, list):
        for v in o:
            _json_price_rows(v, rows, depth + 1)


def _rows_to_records(rows: list, url: str) -> list[dict]:
    seen: set = set()
    out: list[dict] = []
    for name, price in rows:
        if name in seen:
            continue
        seen.add(name)
        out.append({
            "keyword": "", "title": name, "url": url, "domain": get_domain(url),
            "snippet": "", "price": price if len(price) <= 20 else "",
            "category": classify_item(name, "", ""), "character": "", "is_listing": False, "image_url": "",
        })
    return out[:200]


def _items_from_api(soup: BeautifulSoup, html: str, base_url: str) -> list[dict]:
    """探測頁面引用的 JSON API(.json / /api/),直接抓來解析(對付 XHR 動態站)。"""
    cands: list[str] = []
    for m in re.findall(r"""["'](https?:)?(//[^"'\s]+?\.json[^"'\s]*)["']""", html):
        cands.append(("https:" if not m[0] else m[0]) + m[1])
    for m in re.findall(r"""["'](/(?:api|data)/[^"'\s]{3,120})["']""", html):
        cands.append(urljoin(base_url, m))
    seen: set = set()
    uniq: list[str] = []
    for u in cands:
        if u not in seen and u.startswith("http"):
            seen.add(u)
            uniq.append(u)
    rows: list = []
    for api in uniq[:3]:  # 最多探 3 個,避免太慢
        try:
            r = requests.get(api, headers={**_LIGHT_HEADERS, "Accept": "application/json"}, timeout=10)
            if r.status_code >= 400 or "json" not in (r.headers.get("content-type", "")):
                continue
            _json_price_rows(r.json(), rows)
        except Exception:
            continue
        if len(rows) >= 20:
            break
    return _rows_to_records(rows, base_url)


def _items_from_embedded_json(soup: BeautifulSoup, url: str) -> list[dict]:
    """從頁面內嵌 JSON(__NEXT_DATA__ / application/json)抽出「有名稱+價格」的資料列。

    用於 JS 動態渲染(SPA)站:資料常藏在頁面 JSON 裡,靜態 HTML 沒有表格。
    """
    rows: list[tuple[str, str]] = []

    def walk(o, depth=0):
        if depth > 12 or len(rows) > 400:
            return
        if isinstance(o, dict):
            low = {k.lower(): k for k in o.keys()}
            nk = next((low[k] for k in _JSON_NAME_KEYS if k in low), None)
            pk = next((low[k] for k in _JSON_PRICE_KEYS if k in low), None)
            if nk and pk:
                name = o.get(nk)
                price = o.get(pk)
                if isinstance(name, str) and name.strip() and isinstance(price, (int, float, str)) and str(price).strip():
                    pv = str(price)
                    if any(ch.isdigit() for ch in pv):  # 價格要含數字才算
                        rows.append((name.strip(), pv))
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, depth + 1)

    markers = ("__NUXT__", "__INITIAL_STATE__", "__PRELOADED_STATE__", "__APOLLO_STATE__")
    for tag in soup.find_all("script"):
        t = (tag.get("type") or "").lower()
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        if tag.get("id") == "__NEXT_DATA__" or t == "application/json":
            try:
                walk(json.loads(raw))
            except Exception:
                pass
            continue
        # 一般 <script> 內的 SPA 狀態(window.__NUXT__ = {...} 等)
        for mk in markers:
            mi = raw.find(mk)
            if mi < 0:
                continue
            blob = _balanced_json(raw, raw.find("{", mi))
            if blob:
                try:
                    walk(json.loads(blob))
                except Exception:
                    pass
            break

    seen: set = set()
    out: list[dict] = []
    for name, price in rows:
        if name in seen:
            continue
        seen.add(name)
        out.append({
            "keyword": "", "title": name, "url": url, "domain": get_domain(url),
            "snippet": "", "price": price if any(c in price for c in "0123456789") and len(price) <= 20 else "",
            "category": classify_item(name, "", ""), "character": "", "is_listing": False, "image_url": "",
        })
    return out[:200]


def items_from_soup(soup: BeautifulSoup, url: str) -> list[dict]:
    """從已解析的頁面抽出所有表格列 + 內嵌商品(整頁/整站共用)。"""
    out: list[dict] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            title = " | ".join(cells[:6])
            a = tr.find("a", href=True)
            link = urljoin(url, a["href"]) if a else url
            out.append({
                "keyword": "", "title": title, "url": link, "domain": get_domain(link),
                "snippet": "", "price": extract_price(" ".join(cells)),
                "category": classify_item(title, "", ""), "character": "",
                "is_listing": False, "image_url": "",
            })
    out.extend(_extract_listing_products(soup, url, ""))

    # 商品卡:抓指向商品頁的連結(Shopify /products/、WooCommerce 等)+ 鄰近價格
    _price_re = re.compile(r"(NT\$|US\$|RM|HK\$|\$|￥|€|£)\s?[\d,]+(?:\.\d+)?")
    seen_links: set = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not any(m in href.lower() for m in ("/product", "/products/", "/item", "-i.", "/dp/")):
            continue
        title = clean_text(a.get_text(" ", strip=True))
        if not title or len(title) < 2:
            continue
        link = urljoin(url, href)
        if link in seen_links:
            continue
        seen_links.add(link)
        container = a.find_parent(["li", "article", "div"]) or a
        pm = _price_re.search(container.get_text(" ", strip=True))
        out.append({
            "keyword": "", "title": title, "url": link, "domain": get_domain(link),
            "snippet": "", "price": pm.group(0) if pm else "",
            "category": classify_item(title, "", ""), "character": "", "is_listing": False, "image_url": "",
        })

    # 仍沒抓到 → 試內嵌 JSON(SPA 站)
    if not out:
        out.extend(_items_from_embedded_json(soup, url))
    return out


def _feed_items(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """從頁面找 RSS/Atom feed 連結並解析每篇(新聞/部落格最穩)。"""
    feed_url = ""
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        typ = (link.get("type") or "").lower()
        if "alternate" in rel and ("rss" in typ or "atom" in typ or "xml" in typ) and link.get("href"):
            feed_url = urljoin(base_url, link["href"])
            break
    if not feed_url:
        return []
    try:
        fr = requests.get(feed_url, headers=_LIGHT_HEADERS, timeout=12)
        if fr.status_code >= 400:
            return []
        fsoup = BeautifulSoup(fr.text, "xml")
    except Exception:
        return []
    out: list[dict] = []
    for it in fsoup.find_all(["item", "entry"])[:100]:
        title_el = it.find("title")
        title = clean_text(title_el.get_text()) if title_el else ""
        link_el = it.find("link")
        href = ""
        if link_el:
            href = link_el.get("href") or clean_text(link_el.get_text())
        desc_el = it.find("description") or it.find("summary") or it.find("content")
        snippet = clean_text(desc_el.get_text())[:200] if desc_el else ""
        if not title:
            continue
        link = urljoin(base_url, href) if href else feed_url
        out.append({
            "keyword": "", "title": title, "url": link, "domain": get_domain(link),
            "snippet": snippet, "price": "", "category": classify_item(title, snippet, ""),
            "character": "", "is_listing": False, "image_url": "",
        })
    return out


def scrape_full_page(url: str) -> list[dict]:
    """整頁抓取:給一個網址,抓出該頁所有表格列 + 內嵌商品(適合股票/排行/列表頁)。"""
    from . import robots
    if robots.blocked(url):
        raise RuntimeError("此網站在封鎖清單(登入牆/禁止自動抓取)")
    if not robots.allowed(url):
        raise RuntimeError("該網站的 robots.txt 不允許抓取此頁")
    r = requests.get(url, headers=_LIGHT_HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    out = items_from_soup(soup, url)
    if not out:
        out = _feed_items(soup, url)  # 靜態/JSON 都沒有 → 試 RSS/Atom feed
    if not out:
        out = _items_from_api(soup, r.text, url)  # 再試探測頁面引用的 JSON API(XHR 動態站)
    seen: set = set()
    uniq: list[dict] = []
    for x in out:
        k = (x.get("title", ""), x.get("url", ""))
        if x.get("title") and k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq[:500]


def light_enrich(records: list[dict], max_items: int = 24) -> int:
    """為沒有圖片的商品頁(非列表頁)並行補上 og:image(免瀏覽器,雲端可用)。回傳補到幾張。"""
    targets = [r for r in records if not r.get("is_listing") and not r.get("image_url") and r.get("url", "").startswith("http")][:max_items]
    if not targets:
        return 0
    got = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_light_fetch_one, r["url"]): r for r in targets}
        for fut in concurrent.futures.as_completed(futs):
            data = fut.result()
            r = futs[fut]
            if data.get("image_url"):
                r["image_url"] = data["image_url"]
                got += 1
            if data.get("price") and not (r.get("price") or "").strip():
                r["price"] = data["price"]
    return got


def _structured_price(soup: BeautifulSoup) -> str:
    """優先從結構化資料抓價格,比從整頁文字猜可靠得多。

    順序:og:price:amount → itemprop=price → JSON-LD 的 offers.price。
    """
    # og:price:amount
    og_price = soup.find("meta", attrs={"property": "og:price:amount"})
    if og_price and og_price.get("content"):
        currency = soup.find("meta", attrs={"property": "og:price:currency"})
        cur = (currency.get("content") if currency and currency.get("content") else "").strip()
        amount = og_price.get("content").strip()
        if amount:
            return f"{cur} {amount}".strip()

    # microdata itemprop=price
    price_el = soup.find(attrs={"itemprop": "price"})
    if price_el:
        amount = (price_el.get("content") or price_el.get_text(strip=True) or "").strip()
        if amount:
            return amount

    # JSON-LD
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for price in _walk_jsonld_prices(data):
            return price

    return ""


def _fmt_num(v) -> str:
    """把 12345.0 顯示成 12345。"""
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(f)
    except Exception:
        return str(v)


def _walk_jsonld_prices(data) -> list[str]:
    found = []
    if isinstance(data, dict):
        offers = data.get("offers")
        if isinstance(offers, dict):
            currency = offers.get("priceCurrency", "")
            low, high = offers.get("lowPrice"), offers.get("highPrice")
            # AggregateOffer:用真實的價格區間(low–high)
            if low and high and str(low) != str(high):
                found.append(f"{currency} {_fmt_num(low)}–{_fmt_num(high)}".strip())
            elif offers.get("price"):
                found.append(f"{currency} {_fmt_num(offers.get('price'))}".strip())
            elif low:
                found.append(f"{currency} {_fmt_num(low)}".strip())
        elif isinstance(offers, list):
            prices = [o.get("price") for o in offers if isinstance(o, dict) and o.get("price")]
            cur = next((o.get("priceCurrency", "") for o in offers if isinstance(o, dict) and o.get("priceCurrency")), "")
            nums = []
            for p in prices:
                try:
                    nums.append(float(p))
                except Exception:
                    pass
            if len(nums) >= 2 and min(nums) != max(nums):
                found.append(f"{cur} {_fmt_num(min(nums))}–{_fmt_num(max(nums))}".strip())
            elif prices:
                found.append(f"{cur} {_fmt_num(prices[0])}".strip())
        for value in data.values():
            found.extend(_walk_jsonld_prices(value))
    elif isinstance(data, list):
        for item in data:
            found.extend(_walk_jsonld_prices(item))
    return found


def _jsonld_products(data) -> list[dict]:
    res: list[dict] = []
    if isinstance(data, dict):
        t = data.get("@type", "")
        types = t if isinstance(t, list) else [t]
        if "Product" in types:
            res.append(data)
        if "ItemList" in types:
            for el in data.get("itemListElement", []):
                if isinstance(el, dict):
                    res.extend(_jsonld_products(el.get("item", el)))
        for v in data.values():
            if isinstance(v, (dict, list)):
                res.extend(_jsonld_products(v))
    elif isinstance(data, list):
        for x in data:
            res.extend(_jsonld_products(x))
    return res


def _extract_listing_products(soup: BeautifulSoup, base_url: str, keyword: str) -> list[dict]:
    """從列表頁內嵌的結構化資料(JSON-LD)抽出個別商品。"""
    out: list[dict] = []
    seen: set[str] = set()
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for p in _jsonld_products(data):
            name = clean_text(p.get("name", ""))
            url = p.get("url", "") or ""
            if not name or not url:
                continue
            url = urljoin(base_url, url)
            if url in seen:
                continue
            seen.add(url)
            offers = p.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = ""
            if isinstance(offers, dict) and offers.get("price"):
                price = f"{offers.get('priceCurrency', '')} {offers.get('price')}".strip()
            img = p.get("image", "")
            if isinstance(img, list):
                img = img[0] if img else ""
            if isinstance(img, dict):
                img = img.get("url", "")
            out.append({
                "keyword": keyword, "title": name, "url": url, "domain": get_domain(url),
                "snippet": "", "price": price, "image_url": img or "",
                "category": classify_item(name, "", ""), "character": detect_character(name),
                "is_listing": False, "status": "from_listing", "error": "",
            })
    return out[:40]


def scrape_detail_page(driver, item: dict, min_sleep: float = 2, max_sleep: float = 5) -> dict:
    url = item.get("url", "")

    detail = {
        "page_title": "",
        "meta_description": "",
        "h1": "",
        "price": "",
        "image_url": "",
        "key_info": "",
        "category": "",
        "character": "",
        "is_listing": is_listing_url(url),
        "status": "ok",
        "error": "",
    }

    try:
        driver.get(url)
        sleep_random(min_sleep, max_sleep)

        html = driver.page_source

        if looks_like_block_page(html):
            detail["status"] = "blocked_or_captcha"

        soup = BeautifulSoup(html, "lxml")

        if soup.title:
            detail["page_title"] = clean_text(soup.title.get_text())

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            detail["meta_description"] = clean_text(meta_desc.get("content"))

        h1 = soup.find("h1")
        if h1:
            detail["h1"] = clean_text(h1.get_text())

        # 圖片:優先 og:image,其次第一張圖片
        og_img = soup.find("meta", attrs={"property": "og:image"})
        if og_img and og_img.get("content"):
            detail["image_url"] = og_img.get("content")
        else:
            img = soup.find("img")
            if img and img.get("src"):
                detail["image_url"] = img.get("src")

        # 價格:先試結構化資料,再退而從搜尋摘要(通常含真正售價)抓,
        # 最後才從內文猜。避免從整頁雜訊硬抓。
        price = _structured_price(soup)
        if not price:
            price = extract_price(" ".join([item.get("title", ""), item.get("snippet", "")]))
        if not price:
            page_text_head = clean_text(soup.get_text(" ", strip=True))[:2000]
            price = extract_price(page_text_head)
        # 搜尋/列表頁的價格是混雜的(常亂價),不顯示單一價格避免誤導
        detail["price"] = "" if is_listing_url(url) else price
        # 列表頁:嘗試從內嵌結構化資料抽出個別商品
        if is_listing_url(url):
            extra = _extract_listing_products(soup, url, item.get("keyword", ""))
            if extra:
                detail["_extra_products"] = extra

        page_text = clean_text(soup.get_text(" ", strip=True))
        detail["category"] = classify_item(
            item.get("title", ""),
            item.get("snippet", ""),
            page_text[:3000],
        )
        detail["character"] = detect_character(
            item.get("title", ""), item.get("snippet", ""),
            detail["page_title"], detail["h1"], page_text[:1000],
        )

        # 關鍵資訊不要塞爆表格,截前 300 字
        if detail["meta_description"]:
            detail["key_info"] = detail["meta_description"][:300]
        else:
            detail["key_info"] = page_text[:300]

    except Exception as e:
        detail["status"] = "error"
        detail["error"] = str(e)[:300]

    return {**item, **detail}


def classify_search_only(item: dict) -> dict:
    """不進詳細頁時,只用搜尋結果的標題/摘要做分類與價格,讓「不抓詳細」模式也有資料。"""
    _is_listing = is_listing_url(item.get("url", ""))
    enriched = {
        "page_title": "",
        "meta_description": "",
        "h1": "",
        "price": "" if _is_listing else extract_price(" ".join([item.get("title", ""), item.get("snippet", "")])),
        "image_url": "",
        "key_info": clean_text(item.get("snippet", ""))[:300],
        "category": classify_item(item.get("title", ""), item.get("snippet", ""), ""),
        "character": detect_character(item.get("title", ""), item.get("snippet", "")),
        "is_listing": _is_listing,
        "status": "search_only",
        "error": "",
    }
    return {**item, **enriched}
