"""整站爬:從起始網址出發,跟著同網域連結遞迴抓取,每頁抽出表格/商品。

節流 + 頁數/深度上限,避免大量請求被擋。輸出格式與 run_crawl 相同({records, summary})。
"""
import os
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .detail_scraper import items_from_soup, _LIGHT_HEADERS
from .reporter import to_dataframe, build_summary, COLUMN_ORDER
from .utils import get_domain
from . import robots


PREVIEW_CAP = 1000   # 回傳給前端 / 存 run.records 的預覽筆數上限
FLUSH_EVERY = 300    # 每累積這麼多項就 flush 到 DB,記憶體不會一直長


def run_site_crawl(config, on_event=lambda e: None, should_stop=lambda: False, on_batch=None) -> dict:
    """整站爬。大型爬取時用 on_batch(batch) 串流寫入 DB,記憶體只留預覽 + 計數。"""
    start = (config.site_url or "").strip()
    # 安全上限(避免 OOM/逾時);可用 env SITE_MAX_PAGES_CAP 調整,預設 5000
    cap = int(os.environ.get("SITE_MAX_PAGES_CAP", "5000"))
    max_pages = max(1, min(getattr(config, "site_max_pages", 30), cap))
    max_depth = max(0, min(getattr(config, "site_max_depth", 2), 12))
    throttle = max(0.3, float(getattr(config, "min_sleep", 2.0)) * 0.3)

    root = get_domain(start)
    seen = {start}
    queue = [(start, 0)]
    pages = 0

    # 串流統計(不堆全部 records)
    from collections import Counter
    cats: Counter = Counter()
    doms: Counter = Counter()
    total = 0
    with_price = 0
    preview: list[dict] = []
    buffer: list[dict] = []
    seen_k: set = set()

    def _norm(it: dict) -> dict:
        d = {c: it.get(c, "") for c in COLUMN_ORDER}
        d["is_listing"] = bool(it.get("is_listing", False))
        return d

    def _flush():
        nonlocal buffer
        if buffer and on_batch:
            try:
                on_batch(buffer)
            except Exception:
                pass
        buffer = []

    # 選填關鍵字過濾:只收標題/摘要/網址含關鍵字的項目
    from .utils import keyword_tokens, is_relevant
    from urllib.parse import urlparse
    f_tokens = keyword_tokens(getattr(config, "filter_keywords", []) or [])
    path_inc = [p.lower() for p in (getattr(config, "path_includes", []) or [])]

    def _path_ok(u: str) -> bool:
        if not path_inc:
            return True
        p = urlparse(u).path.lower()
        return any(inc in p for inc in path_inc)

    kw_msg = f"、只收含「{'、'.join(config.filter_keywords)}」" if f_tokens else ""
    kw_msg += f"、只抓路徑含「{'、'.join(path_inc)}」" if path_inc else ""
    on_event({"type": "phase", "phase": "starting",
              "message": f"整站爬:{start}(最多 {max_pages} 頁、深度 {max_depth}{kw_msg})"})

    while queue and pages < max_pages:
        if should_stop():
            on_event({"type": "stopped", "message": "已被使用者停止"})
            break
        url, depth = queue.pop(0)
        if robots.blocked(url) or not robots.allowed(url):
            on_event({"type": "warning", "message": f"robots/封鎖清單禁止,略過:{url}"})
            continue
        try:
            r = requests.get(url, headers=_LIGHT_HEADERS, timeout=12)
            ctype = r.headers.get("content-type", "")
            if r.status_code >= 400 or "html" not in ctype:
                continue
            soup = BeautifulSoup(r.text, "lxml")
        except Exception as e:
            on_event({"type": "warning", "message": f"略過 {url}:{str(e)[:80]}"})
            continue

        pages += 1
        items = items_from_soup(soup, url)
        if not _path_ok(url):   # 不在指定路徑的頁面:照樣遞迴找連結,但不收它的項目
            items = []
        if f_tokens:
            items = [it for it in items if is_relevant(it, f_tokens)]

        kept = 0
        for it in items:
            title = (it.get("title") or "").strip()
            k = (title, it.get("url", ""))
            if not title or k in seen_k:
                continue
            seen_k.add(k)
            nit = _norm(it)
            total += 1
            kept += 1
            cats[nit.get("category") or "未分類"] += 1
            doms[nit.get("domain") or "unknown"] += 1
            if (nit.get("price") or "").strip():
                with_price += 1
            if len(preview) < PREVIEW_CAP:
                preview.append(nit)
            buffer.append(nit)
        if len(buffer) >= FLUSH_EVERY:
            _flush()

        on_event({
            "type": "page", "current": pages, "total": max_pages,
            "message": f"[{pages}/{max_pages}] {url} → {kept} 項(累計 {total})",
        })

        if depth < max_depth:
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"]).split("#")[0]
                if link.startswith("http") and get_domain(link) == root and link not in seen:
                    seen.add(link)
                    queue.append((link, depth + 1))

        time.sleep(throttle)

    _flush()
    summary = {
        "total": total, "with_price": with_price,
        "categories": dict(cats.most_common()),
        "domains": dict(doms.most_common(10)),
    }
    note = "" if total <= PREVIEW_CAP else f"(預覽前 {PREVIEW_CAP} 筆,完整 {total} 筆可匯出 CSV)"
    on_event({"type": "done", "summary": summary,
              "message": f"整站爬完成:掃 {pages} 頁、{total} 項 {note}"})
    return {"records": preview, "summary": summary, "total": total, "streamed": total > PREVIEW_CAP}
