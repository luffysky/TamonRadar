from pathlib import Path
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from config import (
    KEYWORDS,
    GOOGLE_PAGES_PER_KEYWORD,
    MAX_DETAIL_PAGES,
    MIN_SLEEP,
    MAX_SLEEP,
    HEADLESS,
    OUTPUT_DIR,
    SKIP_EXTENSIONS,
)
from google_search import search_google
from detail_scraper import scrape_detail_page
from reporter import save_csv, save_excel, save_charts, save_markdown_report
from utils import is_valid_url


def build_driver() -> webdriver.Chrome:
    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=zh-TW")
    options.add_argument("--disable-notifications")

    # 降低被判斷成機器人的機率；不是保證，只是少一點破綻
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    return driver


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


def main() -> None:
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    driver = build_driver()

    try:
        all_search_results = []

        print("開始 Google 搜尋...")
        for keyword in KEYWORDS:
            print(f"搜尋關鍵字：{keyword}")
            results = search_google(
                driver=driver,
                keyword=keyword,
                pages=GOOGLE_PAGES_PER_KEYWORD,
                min_sleep=MIN_SLEEP,
                max_sleep=MAX_SLEEP,
            )
            print(f"  找到 {len(results)} 筆")
            all_search_results.extend(results)

        all_search_results = dedupe_results(all_search_results)
        print(f"去重複後：{len(all_search_results)} 筆")

        # 先存搜尋結果快照，避免中途掛掉整批消失
        search_df = pd.DataFrame(all_search_results)
        search_snapshot = Path(OUTPUT_DIR) / "google_search_results_snapshot.csv"
        search_df.to_csv(search_snapshot, index=False, encoding="utf-8-sig")
        print(f"搜尋結果快照已儲存：{search_snapshot}")

        detail_items = []
        target_items = all_search_results[:MAX_DETAIL_PAGES]

        print(f"開始進入結果頁抓詳細資訊，最多 {len(target_items)} 筆...")
        for index, item in enumerate(target_items, start=1):
            print(f"[{index}/{len(target_items)}] {item.get('title', '')}")
            detail = scrape_detail_page(
                driver=driver,
                item=item,
                min_sleep=MIN_SLEEP,
                max_sleep=MAX_SLEEP,
            )
            detail_items.append(detail)

        df = pd.DataFrame(detail_items)

        # 欄位排序，讓 Excel 比較好讀
        column_order = [
            "keyword",
            "category",
            "title",
            "url",
            "domain",
            "snippet",
            "price",
            "image_url",
            "key_info",
            "page_title",
            "meta_description",
            "h1",
            "google_page",
            "status",
            "error",
        ]

        existing_columns = [col for col in column_order if col in df.columns]
        remaining_columns = [col for col in df.columns if col not in existing_columns]
        df = df[existing_columns + remaining_columns]

        csv_path = save_csv(df, OUTPUT_DIR)
        excel_path = save_excel(df, OUTPUT_DIR)
        chart_paths = save_charts(df, OUTPUT_DIR)
        report_path = save_markdown_report(df, OUTPUT_DIR)

        print("\n完成。輸出檔案：")
        print(f"- CSV: {csv_path}")
        print(f"- Excel: {excel_path}")
        print(f"- Report: {report_path}")
        for path in chart_paths:
            print(f"- Chart: {path}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
