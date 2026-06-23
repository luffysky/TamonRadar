from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from urllib.parse import quote_plus
from utils import clean_text, normalize_google_url, get_domain, sleep_random, looks_like_block_page


def search_google(driver, keyword: str, pages: int = 1, min_sleep: int = 2, max_sleep: int = 5) -> list[dict]:
    results = []

    for page in range(pages):
        start = page * 10
        url = f"https://www.google.com/search?q={quote_plus(keyword)}&start={start}&hl=zh-TW"
        driver.get(url)
        sleep_random(min_sleep, max_sleep)

        html = driver.page_source
        if looks_like_block_page(html):
            print("\nGoogle 可能出現 CAPTCHA / unusual traffic。")
            input("請在 Chrome 內手動處理後，回到終端機按 Enter 繼續...")

        # Google 搜尋結果 DOM 常變，所以用多種 selector 兼容
        blocks = driver.find_elements(By.CSS_SELECTOR, "div.g, div.MjjYud")

        for block in blocks:
            try:
                link_el = block.find_element(By.CSS_SELECTOR, "a")
                raw_url = link_el.get_attribute("href")
                result_url = normalize_google_url(raw_url)

                title = ""
                try:
                    title = block.find_element(By.CSS_SELECTOR, "h3").text
                except Exception:
                    title = link_el.text

                snippet = ""
                snippet_selectors = [
                    "div.VwiC3b",
                    "span.aCOpRe",
                    "div.IsZvec",
                    "div[data-sncf]"
                ]
                for selector in snippet_selectors:
                    try:
                        snippet = block.find_element(By.CSS_SELECTOR, selector).text
                        if snippet:
                            break
                    except Exception:
                        pass

                title = clean_text(title)
                snippet = clean_text(snippet)

                if not title or not result_url.startswith("http"):
                    continue

                results.append({
                    "keyword": keyword,
                    "title": title,
                    "url": result_url,
                    "domain": get_domain(result_url),
                    "snippet": snippet,
                    "google_page": page + 1,
                })

            except Exception:
                continue

    return results
