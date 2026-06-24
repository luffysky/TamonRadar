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


def _walk_jsonld_prices(data) -> list[str]:
    found = []
    if isinstance(data, dict):
        offers = data.get("offers")
        if isinstance(offers, dict):
            price = offers.get("price")
            currency = offers.get("priceCurrency", "")
            if price:
                found.append(f"{currency} {price}".strip())
        elif isinstance(offers, list):
            for off in offers:
                if isinstance(off, dict) and off.get("price"):
                    found.append(f"{off.get('priceCurrency', '')} {off.get('price')}".strip())
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
