"""整站爬:從起始網址出發,跟著同網域連結遞迴抓取,每頁抽出表格/商品。

節流 + 頁數/深度上限,避免大量請求被擋。輸出格式與 run_crawl 相同({records, summary})。
"""
import os
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .detail_scraper import items_from_soup, _LIGHT_HEADERS
from .reporter import to_dataframe, build_summary
from .utils import get_domain
from . import robots


def run_site_crawl(config, on_event=lambda e: None, should_stop=lambda: False) -> dict:
    start = (config.site_url or "").strip()
    # 安全上限(避免 OOM/逾時);可用 env SITE_MAX_PAGES_CAP 調整,預設 5000
    cap = int(os.environ.get("SITE_MAX_PAGES_CAP", "5000"))
    max_pages = max(1, min(getattr(config, "site_max_pages", 30), cap))
    max_depth = max(0, min(getattr(config, "site_max_depth", 2), 12))
    throttle = max(0.3, float(getattr(config, "min_sleep", 2.0)) * 0.3)

    root = get_domain(start)
    seen = {start}
    queue = [(start, 0)]
    records: list[dict] = []
    pages = 0

    on_event({"type": "phase", "phase": "starting",
              "message": f"整站爬:{start}(最多 {max_pages} 頁、深度 {max_depth})"})

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
        records.extend(items)
        on_event({
            "type": "page", "current": pages, "total": max_pages,
            "message": f"[{pages}/{max_pages}] {url} → {len(items)} 項",
        })

        if depth < max_depth:
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"]).split("#")[0]
                if link.startswith("http") and get_domain(link) == root and link not in seen:
                    seen.add(link)
                    queue.append((link, depth + 1))

        time.sleep(throttle)

    # 去重
    seen_k: set = set()
    uniq: list[dict] = []
    for x in records:
        k = (x.get("title", ""), x.get("url", ""))
        if x.get("title") and k not in seen_k:
            seen_k.add(k)
            uniq.append(x)

    df = to_dataframe(uniq)
    summary = build_summary(df)
    on_event({"type": "done", "summary": summary,
              "message": f"整站爬完成:掃 {pages} 頁、{summary['total']} 項"})
    return {"records": df.to_dict(orient="records"), "summary": summary}
