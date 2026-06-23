"""價格雷達:比較這次與上次的爬蟲結果,找出新品、降價、補貨。"""
import money

_MAX_LIST = 50


def _slim(r: dict, extra: dict | None = None) -> dict:
    base = {
        "title": r.get("title", ""),
        "url": r.get("url", ""),
        "domain": r.get("domain", ""),
        "category": r.get("category", ""),
        "price": r.get("price", ""),
        "price_twd": money.to_twd(r.get("price", "")),
        "image_url": r.get("image_url", ""),
    }
    if extra:
        base.update(extra)
    return base


def compute_diff(current: list[dict], previous: list[dict]) -> dict:
    prev_by_url = {r.get("url"): r for r in previous if r.get("url")}

    new_items: list[dict] = []
    price_drops: list[dict] = []
    restock: list[dict] = []

    for r in current:
        url = r.get("url")
        if not url:
            continue
        cur_twd = money.to_twd(r.get("price", ""))
        prev = prev_by_url.get(url)

        if prev is None:
            new_items.append(_slim(r))
            continue

        old_twd = money.to_twd(prev.get("price", ""))
        if old_twd and cur_twd and cur_twd < old_twd:
            pct = round((old_twd - cur_twd) / old_twd * 100)
            price_drops.append(_slim(r, {
                "old_price": prev.get("price", ""),
                "old_twd": old_twd,
                "drop_pct": pct,
            }))
        elif not old_twd and cur_twd:
            # 之前沒偵測到價格、現在有 → 視為(可能)補貨/上架
            restock.append(_slim(r))

    # 降價幅度大的排前面
    price_drops.sort(key=lambda x: x.get("drop_pct", 0), reverse=True)

    return {
        "counts": {
            "new": len(new_items),
            "price_drops": len(price_drops),
            "restock": len(restock),
        },
        "new_items": new_items[:_MAX_LIST],
        "price_drops": price_drops[:_MAX_LIST],
        "restock": restock[:_MAX_LIST],
    }
