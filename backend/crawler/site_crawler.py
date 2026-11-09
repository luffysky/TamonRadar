"""整站爬:從起始網址出發,跟著同網域連結遞迴抓取,每頁抽出表格/商品。

節流 + 頁數/深度上限,避免大量請求被擋。輸出格式與 run_crawl 相同({records, summary})。
"""
import os
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collections import Counter

from .config import BudgetExhausted
from .detail_scraper import items_from_soup, _LIGHT_HEADERS
from .reporter import to_dataframe, build_summary, COLUMN_ORDER
from .utils import get_domain
from . import robots
from safe_fetch import safe_get


PREVIEW_CAP = 1000   # 回傳給前端 / 存 run.records 的預覽筆數上限


class MemoryStore:
    """沒有資料庫斷點時的存放(同步呼叫/測試);正式環境用 jobs.DbSiteStore,介面相同。"""

    def __init__(self):
        self.pages = 0
        self.total = 0
        self.with_price = 0
        self.cats: Counter = Counter()
        self.doms: Counter = Counter()
        self._seen: set[str] = set()
        self._queue: list[tuple[str, int]] = []
        self._seen_items: set[tuple] = set()
        self._preview: list[dict] = []

    def seed(self, start: str) -> None:
        self._seen.add(start)
        self._queue.append((start, 0))

    def next(self) -> tuple[str, int] | None:
        return self._queue.pop(0) if self._queue else None

    def skip(self, url: str) -> None:
        pass

    def commit_page(self, url: str, items: list[dict], links: list[tuple[str, int]]) -> int:
        kept = 0
        self.pages += 1
        for it in items:
            k = (it.get("title", ""), it.get("url", ""))
            if k in self._seen_items:
                continue
            self._seen_items.add(k)
            kept += 1
            self.total += 1
            self.cats[it.get("category") or "未分類"] += 1
            self.doms[it.get("domain") or "unknown"] += 1
            if (it.get("price") or "").strip():
                self.with_price += 1
            if len(self._preview) < PREVIEW_CAP:
                self._preview.append(it)
        for link, depth in links:
            if link not in self._seen:
                self._seen.add(link)
                self._queue.append((link, depth))
        return kept

    def preview(self, cap: int) -> list[dict]:
        return self._preview[:cap]


def run_site_crawl(config, on_event=lambda e: None, should_stop=lambda: False, store=None,
                   budget_left=lambda: True) -> dict:
    """整站爬。store 保存佇列/去重/計數;每頁一個原子單位,時間預算用完丟 BudgetExhausted。"""
    start = (config.site_url or "").strip()
    # 安全上限(避免 OOM/逾時);可用 env SITE_MAX_PAGES_CAP 調整,預設 5000
    cap = int(os.environ.get("SITE_MAX_PAGES_CAP", "5000"))
    max_pages = max(1, min(getattr(config, "site_max_pages", 30), cap))
    max_depth = max(0, min(getattr(config, "site_max_depth", 2), 12))
    throttle = max(0.3, float(getattr(config, "min_sleep", 2.0)) * 0.3)

    store = store if store is not None else MemoryStore()
    root = get_domain(start)

    def _norm(it: dict) -> dict:
        d = {c: it.get(c, "") for c in COLUMN_ORDER}
        d["is_listing"] = bool(it.get("is_listing", False))
        return d

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

    store.seed(start)

    while store.pages < max_pages:
        if should_stop():
            on_event({"type": "stopped", "message": "已被使用者停止"})
            break
        if not budget_left():
            raise BudgetExhausted()
        nxt = store.next()
        if nxt is None:
            break
        url, depth = nxt
        if robots.blocked(url) or not robots.allowed(url):
            on_event({"type": "warning", "message": f"robots/封鎖清單禁止,略過:{url}"})
            store.skip(url)
            continue
        try:
            r = safe_get(url, headers=_LIGHT_HEADERS, timeout=12)
            ctype = r.headers.get("content-type", "")
            if r.status_code >= 400 or "html" not in ctype:
                store.skip(url)
                continue
            soup = BeautifulSoup(r.text, "lxml")
        except Exception as e:
            on_event({"type": "warning", "message": f"略過 {url}:{str(e)[:80]}"})
            store.skip(url)
            continue

        items = items_from_soup(soup, url)
        if not _path_ok(url):   # 不在指定路徑的頁面:照樣遞迴找連結,但不收它的項目
            items = []
        if f_tokens:
            items = [it for it in items if is_relevant(it, f_tokens)]
        items = [_norm(it) for it in items if (it.get("title") or "").strip()]

        links: list[tuple[str, int]] = []
        if depth < max_depth:
            for a in soup.find_all("a", href=True):
                link = urljoin(url, a["href"]).split("#")[0]
                if link.startswith("http") and get_domain(link) == root:
                    links.append((link, depth + 1))

        kept = store.commit_page(url, items, links)
        on_event({
            "type": "page", "current": store.pages, "total": max_pages,
            "message": f"[{store.pages}/{max_pages}] {url} → {kept} 項(累計 {store.total})",
        })
        time.sleep(throttle)

    total = store.total
    summary = {
        "total": total, "with_price": store.with_price,
        "categories": dict(store.cats.most_common()),
        "domains": dict(store.doms.most_common(10)),
    }
    note = "" if total <= PREVIEW_CAP else f"(預覽前 {PREVIEW_CAP} 筆,完整 {total} 筆可匯出 CSV)"
    on_event({"type": "done", "summary": summary,
              "message": f"整站爬完成:掃 {store.pages} 頁、{total} 項 {note}"})
    return {"records": store.preview(PREVIEW_CAP), "summary": summary, "total": total, "streamed": total > PREVIEW_CAP}
