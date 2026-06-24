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
        "price_stats": stats,
        "histogram": histogram,
        "good_deals": good_deals[:10],
        "outliers": outliers[:8],
        "clusters": multi,
        "status_dist": status_dist,
        "trust_dist": trust_dist,
        "cheapest": cheapest,
        "best_value": best,
    }
