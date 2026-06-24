"""深度情報引擎:把零散搜尋結果變成可比價的商品情報。

產出:行情基準、划算分數、現貨/代購/二手狀態、同商品跨站聚合、來源可信度、價格分佈。
"""
import difflib
import re
import statistics

import money

# 狀態關鍵字(優先序:缺貨 > 預購 > 代購 > 二手 > 現貨)
_STATUS_RULES = [
    ("缺貨", ["缺貨", "售完", "完售", "sold out", "out of stock", "已售完", "補貨中"]),
    ("預購", ["預購", "pre-order", "preorder", "預訂", "預約", "到貨"]),
    ("代購", ["代購", "代标", "代標", "代購服務", "proxy"]),
    ("二手", ["二手", "中古", "preowned", "used", "二手品"]),
    ("現貨", ["現貨", "in stock", "現品", "立即出貨", "快速到貨"]),
]

# 來源可信度
_AUCTION = ["ruten.com", "找", "拍賣", "auctions", "yahoo.co.jp/auction", "mercari", "carousell"]
_MARKET = ["shopee", "momoshop", "pchome", "books.com", "rakuten", "amazon", "ebay", "yahoo", "etmall", "biggo"]


def _status(text: str) -> str:
    low = text.lower()
    for label, kws in _STATUS_RULES:
        if any(k.lower() in low for k in kws):
            return label
    return ""


def _trust(domain: str) -> str:
    d = (domain or "").lower()
    if any(k in d for k in _AUCTION):
        return "拍賣/個人"
    if any(k in d for k in _MARKET):
        return "商城/平台"
    return "官網/其他"


_NOISE = re.compile(r"[\s\-_/|,，。、!?:;()\[\]{}「」『』#*]+")
_SIZE = re.compile(r"\b(\d+(\.\d+)?(cm|mm|吋|公分|inch|g|kg|ml)|s|m|l|xl|xxl)\b", re.I)


def _norm_title(t: str) -> str:
    t = (t or "").lower()
    t = _SIZE.sub(" ", t)
    t = _NOISE.sub(" ", t)
    return t.strip()


def _cluster(items: list[dict]) -> list[dict]:
    """用標題相似度把同商品的不同賣場聚成一組(難 O(n^2),結果通常 < 數百筆)。"""
    norms = [_norm_title(it["title"]) for it in items]
    used = [False] * len(items)
    clusters = []
    for i in range(len(items)):
        if used[i] or not norms[i]:
            continue
        group = [i]
        used[i] = True
        for j in range(i + 1, len(items)):
            if used[j] or not norms[j]:
                continue
            if difflib.SequenceMatcher(None, norms[i], norms[j]).ratio() >= 0.72:
                group.append(j)
                used[j] = True
        members = [items[k] for k in group]
        priced = [m for m in members if m.get("price_twd")]
        cheapest = min(priced, key=lambda m: m["price_twd"]) if priced else None
        clusters.append({
            "title": items[i]["title"],
            "count": len(members),
            "domains": sorted({m["domain"] for m in members if m.get("domain")}),
            "min_twd": cheapest["price_twd"] if cheapest else None,
            "cheapest_url": cheapest["url"] if cheapest else "",
            "cheapest_domain": cheapest["domain"] if cheapest else "",
            "members": members,
        })
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def _num(s: str) -> float | None:
    m = re.search(r"[\d,]+(?:\.\d+)?", s or "")
    return float(m.group(0).replace(",", "")) if m else None


def _dist(items: list[dict], extract) -> list[dict]:
    d: dict = {}
    for it in items:
        v = extract(it)
        if v:
            d[v] = d.get(v, 0) + 1
    return [{"name": k, "count": v} for k, v in sorted(d.items(), key=lambda x: -x[1])][:10]


def _range_facet(label: str, values: list[float], unit: str) -> dict | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    return {"type": "range", "label": label, "unit": unit,
            "min": round(vals[0], 1), "max": round(vals[-1], 1),
            "median": round(vals[n // 2], 1), "count": n}


# 各垂直的地區關鍵字(取最常見台灣縣市)
_REGIONS = ["台北", "臺北", "新北", "桃園", "台中", "臺中", "台南", "臺南", "高雄", "新竹", "基隆",
            "嘉義", "宜蘭", "花蓮", "台東", "臺東", "屏東", "雲林", "彰化", "南投", "苗栗", "澎湖", "金門"]


def _region_of(it: dict) -> str:
    blob = f"{it['title']} {it.get('snippet','')}"
    for r in _REGIONS:
        if r in blob:
            return r.replace("臺", "台")
    return ""


def _facets(items: list[dict], vertical: str) -> list[dict]:
    """依垂直產生專屬分析面向(facets)。"""
    facets: list[dict] = []
    blob = lambda it: f"{it['title']} {it.get('snippet','')}"  # noqa: E731

    if vertical == "food":
        ratings = []
        for it in items:
            m = re.search(r"([0-5](?:\.\d)?)\s*(?:顆星|星|★|分|/5)", blob(it))
            if m:
                ratings.append(float(m.group(1)))
        r = _range_facet("評分", ratings, "★")
        if r:
            facets.append(r)
        facets.append({"type": "dist", "label": "地區分佈", "items": _dist(items, _region_of)})
        facets.append({"type": "dist", "label": "類型", "items": _dist(items, lambda it: next(
            (k for k in ["火鍋", "燒肉", "壽司", "拉麵", "咖啡", "甜點", "早午餐", "牛排", "素食", "小吃", "吃到飽"] if k in blob(it)), ""))})

    elif vertical in ("job", "創業", "職缺"):
        sals = []
        for it in items:
            for m in re.finditer(r"(?:月薪|年薪|時薪|NT\$|薪資)\s*([\d,]+)", blob(it)):
                sals.append(float(m.group(1).replace(",", "")))
        r = _range_facet("薪資出現值", sals, "")
        if r:
            facets.append(r)
        facets.append({"type": "dist", "label": "地區分佈", "items": _dist(items, _region_of)})
        facets.append({"type": "dist", "label": "工作型態", "items": _dist(items, lambda it: next(
            (k for k in ["遠端", "在家", "兼職", "正職", "實習", "派遣", "接案"] if k in blob(it)), ""))})

    elif vertical in ("realestate", "房產", "房地產"):
        prices = [_num(re.sub(r".*?", "", "")) for _ in []]
        totals, pings, ages = [], [], []
        for it in items:
            b = blob(it)
            mt = re.search(r"([\d,]+)\s*萬", b)
            if mt:
                totals.append(float(mt.group(1).replace(",", "")))
            mp = re.search(r"([\d.]+)\s*坪", b)
            if mp:
                pings.append(float(mp.group(1)))
            ma = re.search(r"(?:屋齡)\s*([\d.]+)", b)
            if ma:
                ages.append(float(ma.group(1)))
        for f in (_range_facet("總價", totals, "萬"), _range_facet("坪數", pings, "坪"), _range_facet("屋齡", ages, "年")):
            if f:
                facets.append(f)
        facets.append({"type": "dist", "label": "地區分佈", "items": _dist(items, _region_of)})

    elif vertical in ("travel", "旅遊"):
        nights, stars = [], []
        for it in items:
            b = blob(it)
            mn = re.search(r"(\d+)\s*天", b)
            if mn:
                nights.append(float(mn.group(1)))
            ms = re.search(r"([1-5])\s*星", b)
            if ms:
                stars.append(float(ms.group(1)))
        for f in (_range_facet("天數", nights, "天"), _range_facet("星等", stars, "★")):
            if f:
                facets.append(f)
        facets.append({"type": "dist", "label": "目的地", "items": _dist(items, _region_of)})

    elif vertical in ("course", "health", "課程", "健康"):
        hours, ratings = [], []
        for it in items:
            b = blob(it)
            mh = re.search(r"([\d.]+)\s*(?:小時|時數|hr)", b)
            if mh:
                hours.append(float(mh.group(1)))
            mr = re.search(r"([0-5](?:\.\d)?)\s*(?:星|★|分)", b)
            if mr:
                ratings.append(float(mr.group(1)))
        for f in (_range_facet("時數", hours, "小時"), _range_facet("評分", ratings, "★")):
            if f:
                facets.append(f)
        facets.append({"type": "dist", "label": "難度", "items": _dist(items, lambda it: next(
            (k for k in ["入門", "初級", "中級", "進階", "高級", "零基礎"] if k in blob(it)), ""))})

    elif vertical in ("pet", "animal", "寵物", "動物"):
        facets.append({"type": "dist", "label": "類別", "items": _dist(items, lambda it: next(
            (k for k in ["貓", "狗", "兔", "鼠", "鳥", "魚", "爬蟲"] if k in blob(it)), ""))})
        facets.append({"type": "dist", "label": "性質", "items": _dist(items, lambda it: next(
            (k for k in ["送養", "認養", "領養", "販售", "出售", "走失", "協尋"] if k in blob(it)), ""))})
        facets.append({"type": "dist", "label": "地區分佈", "items": _dist(items, _region_of)})

    elif vertical in ("stock", "crypto", "股市", "加密貨幣"):
        ups = sum(1 for it in items if any(k in blob(it) for k in ["漲", "上漲", "+"]))
        downs = sum(1 for it in items if any(k in blob(it) for k in ["跌", "下跌", "-"]))
        facets.append({"type": "dist", "label": "情緒傾向", "items": [{"name": "偏多/漲", "count": ups}, {"name": "偏空/跌", "count": downs}]})

    # 共通:來源分佈(所有垂直都有用)
    facets.append({"type": "dist", "label": "來源網站", "items": _dist(items, lambda it: it.get("domain", ""))})
    return [f for f in facets if f and (f.get("items") or f.get("median") is not None)]


def deep_insights(records: list[dict], vertical: str = "") -> dict:
    items = []
    for r in records or []:
        title = (r.get("title") or "").strip()
        if not title:
            continue
        blob = f"{title} {r.get('snippet', '')}"
        twd = money.to_twd(r.get("price"))
        items.append({
            "title": title, "url": r.get("url", ""), "domain": r.get("domain", ""),
            "price": r.get("price", ""), "price_twd": twd, "image_url": r.get("image_url", ""),
            "category": r.get("category", ""), "status": _status(blob), "trust": _trust(r.get("domain", "")),
        })

    priced = [it["price_twd"] for it in items if it["price_twd"]]
    stats = {}
    good_deals = []
    outliers = []
    if priced:
        priced_sorted = sorted(priced)
        median = statistics.median(priced_sorted)
        n = len(priced_sorted)
        p25 = priced_sorted[max(0, int(n * 0.25) - 0)] if n >= 4 else priced_sorted[0]
        p75 = priced_sorted[min(n - 1, int(n * 0.75))] if n >= 4 else priced_sorted[-1]
        stats = {
            "count": n, "min": priced_sorted[0], "max": priced_sorted[-1],
            "median": int(median), "avg": int(sum(priced_sorted) / n), "p25": int(p25), "p75": int(p75),
        }
        # 划算分數:相對行情中位數,越低越划算(0~100)
        for it in items:
            if not it["price_twd"]:
                it["deal_score"] = None
                continue
            ratio = it["price_twd"] / median if median else 1
            score = max(0, min(100, round((1.4 - ratio) / 1.4 * 100)))
            if it["status"] == "缺貨":
                score = max(0, score - 30)
            if it["trust"] == "官網/其他":
                score = min(100, score + 5)
            it["deal_score"] = score
            disc = round((1 - ratio) * 100)
            if ratio <= 0.85 and it["status"] != "缺貨":
                good_deals.append({**it, "discount_pct": disc})
            # 離群:過低(<行情 35%,疑假貨/標錯)或過高(>行情 250%)
            if ratio < 0.35:
                outliers.append({**it, "reason": "價格異常偏低(留意真偽/標錯價)"})
            elif ratio > 2.5:
                outliers.append({**it, "reason": "價格異常偏高"})
        good_deals.sort(key=lambda x: x["price_twd"])
    else:
        for it in items:
            it["deal_score"] = None

    # 直方圖(5 桶)
    histogram = []
    if priced and stats.get("max", 0) > stats.get("min", 0):
        lo, hi = stats["min"], stats["max"]
        step = max(1, (hi - lo) // 5)
        buckets = [0] * 5
        for v in priced:
            idx = min(4, (v - lo) // step)
            buckets[idx] += 1
        for i, c in enumerate(buckets):
            histogram.append({"range": f"{lo + i * step:,}–{lo + (i + 1) * step:,}", "count": c})

    clusters = _cluster(items)
    multi = [c for c in clusters if c["count"] >= 2][:20]

    status_dist: dict = {}
    trust_dist: dict = {}
    for it in items:
        if it["status"]:
            status_dist[it["status"]] = status_dist.get(it["status"], 0) + 1
        trust_dist[it["trust"]] = trust_dist.get(it["trust"], 0) + 1

    cheapest = min((it for it in items if it["price_twd"]), key=lambda x: x["price_twd"], default=None)
    best = max((it for it in items if it.get("deal_score") is not None), key=lambda x: x["deal_score"], default=None)

    return {
        "total": len(items),
        "vertical": vertical,
        "price_stats": stats,
        "histogram": histogram,
        "good_deals": good_deals[:10],
        "outliers": outliers[:8],
        "clusters": multi,
        "status_dist": status_dist,
        "trust_dist": trust_dist,
        "cheapest": cheapest,
        "best_value": best,
        "facets": _facets(items, vertical),
    }
