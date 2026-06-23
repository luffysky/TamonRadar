"""爬蟲總指揮:由原本的 main.py 重構而來。

差別:
- 不再寫死設定,改吃 CrawlConfig。
- 每個階段透過 on_event callback 即時回報進度(給 SSE 串流用)。
- 回傳結構化結果(records + summary),而不是只寫檔。
"""
import os
from pathlib import Path
from typing import Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from .config import CrawlConfig, SKIP_EXTENSIONS
from .google_search import search_google, BlockedError
from .detail_scraper import scrape_detail_page, classify_search_only
from .reporter import to_dataframe, build_summary
from .utils import is_valid_url

EventCallback = Callable[[dict], None]


def _noop(event: dict) -> None:
    pass


def build_driver(headless: bool) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=zh-TW")
    options.add_argument("--disable-notifications")
    # 容器/雲端環境必備,否則 Chrome 會因權限或共享記憶體不足而崩潰
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 部署時用容器內的 chromium / chromedriver(由 Dockerfile 設定環境變數);
    # 本機沒設這些變數時,退回 webdriver-manager 自動下載對應 driver。
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    driver_path = os.environ.get("CHROMEDRIVER")
    if driver_path:
        service = Service(driver_path)
    else:
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)


def dedupe_results(items: list[dict]) -> list[dict]:
    seen = set()
    final = []
    for item in items:
        url = item.get("url", "")
        if not is_valid_url(url, SKIP_EXTENSIONS):
            continue
        if url in seen:
            continue
        seen.add(url)
        final.append(item)
    return final


def run_crawl(
    config: CrawlConfig,
    on_event: EventCallback = _noop,
    should_stop: Callable[[], bool] = lambda: False,
) -> dict:
    """執行一次完整爬蟲。回傳 {records, summary}。"""
    config = config.normalized()
    on_event({"type": "phase", "phase": "starting", "message": "啟動瀏覽器中..."})

    driver = build_driver(config.headless)
    try:
        all_search_results: list[dict] = []

        total_kw = len(config.keywords)
        for idx, keyword in enumerate(config.keywords, start=1):
            if should_stop():
                on_event({"type": "stopped", "message": "已被使用者停止"})
                break
            on_event({
                "type": "search_keyword",
                "message": f"搜尋關鍵字:{keyword}",
                "current": idx, "total": total_kw, "keyword": keyword,
            })
            try:
                results = search_google(
                    driver=driver,
                    keyword=keyword,
                    pages=config.google_pages_per_keyword,
                    min_sleep=config.min_sleep,
                    max_sleep=config.max_sleep,
                )
                on_event({
                    "type": "search_done", "keyword": keyword,
                    "found": len(results), "message": f"「{keyword}」找到 {len(results)} 筆",
                })
                all_search_results.extend(results)
            except BlockedError as e:
                on_event({"type": "blocked", "keyword": keyword, "message": str(e)})
                continue

        deduped = dedupe_results(all_search_results)
        on_event({
            "type": "dedup", "count": len(deduped),
            "message": f"去重複後共 {len(deduped)} 筆",
        })

        if not config.scrape_details or config.max_detail_pages == 0:
            records = [classify_search_only(item) for item in deduped]
        else:
            targets = deduped[: config.max_detail_pages]
            records = []
            total = len(targets)
            on_event({
                "type": "phase", "phase": "detail",
                "message": f"開始抓詳細資訊,共 {total} 筆",
            })
            for i, item in enumerate(targets, start=1):
                if should_stop():
                    on_event({"type": "stopped", "message": "已被使用者停止"})
                    break
                detail = scrape_detail_page(
                    driver=driver, item=item,
                    min_sleep=config.min_sleep, max_sleep=config.max_sleep,
                )
                records.append(detail)
                on_event({
                    "type": "detail_progress", "current": i, "total": total,
                    "title": item.get("title", ""), "category": detail.get("category", ""),
                    "price": detail.get("price", ""),
                    "message": f"[{i}/{total}] {item.get('title', '')}",
                })
            # 沒抓到詳細頁的剩餘搜尋結果也帶上(只有標題/摘要層級資料)
            for item in deduped[len(records):]:
                records.append(classify_search_only(item))

        df = to_dataframe(records)
        summary = build_summary(df)
        on_event({
            "type": "done",
            "summary": summary,
            "message": f"完成,共 {summary['total']} 筆",
        })
        return {"records": df.to_dict(orient="records"), "summary": summary}

    finally:
        try:
            driver.quit()
        except Exception:
            pass
