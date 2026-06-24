"""爬蟲總指揮:由原本的 main.py 重構而來。

差別:
- 不再寫死設定,改吃 CrawlConfig。
- 每個階段透過 on_event callback 即時回報進度(給 SSE 串流用)。
- 回傳結構化結果(records + summary),而不是只寫檔。
"""
import os
from dataclasses import replace
from pathlib import Path
from typing import Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from .config import CrawlConfig, SKIP_EXTENSIONS
from .google_search import search_google, BlockedError
from .search_api import search_api, SearchApiError, resolve_order, API_PROVIDERS
from .detail_scraper import scrape_detail_page, classify_search_only, light_enrich
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
    use_api = config.search_provider in API_PROVIDERS
    # 雲端輕量映像沒有 Chrome:設 DISABLE_BROWSER=1 就完全不嘗試開瀏覽器(避免 chromedriver 127 錯誤與等待)
    browser_disabled = os.environ.get("DISABLE_BROWSER") == "1"
    if browser_disabled and config.scrape_details:
        on_event({"type": "warning", "message": "此環境未安裝瀏覽器(DISABLE_BROWSER=1),已自動關閉「進詳細頁」,只用搜尋結果。"})
        config = replace(config, scrape_details=False)
    need_driver = (not use_api) or config.scrape_details

    driver = None
    try:
        if browser_disabled and need_driver and not use_api:
            on_event({"type": "error", "message": "此環境未安裝瀏覽器,無法使用 Selenium 搜尋,請改用搜尋 API(如 DuckDuckGo)。"})
            return {"records": [], "summary": build_summary(to_dataframe([]))}
        # 只有需要時才開 Chrome:用 API 搜尋又不抓詳細頁,就完全不需要瀏覽器(雲端友善)
        if need_driver:
            on_event({"type": "phase", "phase": "starting", "message": "啟動瀏覽器中..."})
            try:
                driver = build_driver(config.headless)
            except Exception as e:
                if use_api:
                    # 搜尋用 API 沒問題,只是開不了瀏覽器 → 降級成不進詳細頁,不讓整批失敗
                    on_event({"type": "warning",
                              "message": f"瀏覽器啟動失敗,改為只用搜尋結果(不進詳細頁):{e}"})
                    config = replace(config, scrape_details=False)
                    driver = None
                else:
                    raise
        else:
            on_event({"type": "phase", "phase": "starting",
                      "message": f"使用搜尋 API:{config.search_provider}"})

        all_search_results: list[dict] = []

        # 搜尋 API 的嘗試順序(例:serpapi→brave),額度用完的會被標記跳過
        api_order = resolve_order(config.search_provider) if use_api else []
        api_dead: set[str] = set()

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
            if use_api:
                results = None
                for prov in api_order:
                    if prov in api_dead:
                        continue
                    try:
                        results = search_api(prov, keyword, config.google_pages_per_keyword)
                        break
                    except SearchApiError as e:
                        # 這個 provider 不可用(沒金鑰/額度用完)→ 標記跳過,改用下一個
                        on_event({"type": "warning", "message": f"{prov} 不可用,改用備援:{e}"})
                        api_dead.add(prov)
                        continue
                if results is None:
                    on_event({"type": "error", "message": "所有搜尋 API 都不可用(沒金鑰或額度用完)"})
                    break
            else:
                try:
                    results = search_google(
                        driver=driver,
                        keyword=keyword,
                        pages=config.google_pages_per_keyword,
                        min_sleep=config.min_sleep,
                        max_sleep=config.max_sleep,
                    )
                except BlockedError as e:
                    # Selenium 被 Google 擋(雲端常見)→ 若有搜尋 API 金鑰就自動改用
                    fallback = resolve_order("serpapi")
                    if not fallback:
                        on_event({"type": "blocked", "keyword": keyword, "message": str(e)})
                        continue
                    on_event({"type": "warning",
                              "message": f"Selenium 被 Google 攔截,自動改用搜尋 API({fallback[0]})"})
                    use_api = True
                    api_order = fallback
                    results = None
                    for prov in api_order:
                        if prov in api_dead:
                            continue
                        try:
                            results = search_api(prov, keyword, config.google_pages_per_keyword)
                            break
                        except SearchApiError as e2:
                            on_event({"type": "warning", "message": f"{prov} 不可用:{e2}"})
                            api_dead.add(prov)
                    if results is None:
                        on_event({"type": "error", "message": "搜尋 API 也不可用(沒金鑰或額度用完)"})
                        break

            on_event({
                "type": "search_done", "keyword": keyword,
                "found": len(results), "message": f"「{keyword}」找到 {len(results)} 筆",
            })
            all_search_results.extend(results)

        deduped = dedupe_results(all_search_results)
        on_event({
            "type": "dedup", "count": len(deduped),
            "message": f"去重複後共 {len(deduped)} 筆",
        })

        if not config.scrape_details or config.max_detail_pages == 0:
            records = [classify_search_only(item) for item in deduped]
            # 沒進詳細頁(雲端/API 模式)→ 用 requests 並行補商品圖(og:image),免瀏覽器
            on_event({"type": "phase", "phase": "enrich", "message": "補商品圖片中..."})
            try:
                got = light_enrich(records, max_items=24)
                if got:
                    on_event({"type": "info", "message": f"補到 {got} 張商品圖"})
            except Exception:
                pass
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
                extra = detail.pop("_extra_products", []) if isinstance(detail, dict) else []
                records.append(detail)
                if extra:
                    records.extend(extra)
                    on_event({"type": "info", "message": f"從列表頁多抓到 {len(extra)} 個商品"})
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
