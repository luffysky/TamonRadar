from selenium.webdriver.common.by import By
from urllib.parse import quote_plus

from .utils import (
    clean_text,
    normalize_google_url,
    get_domain,
    sleep_random,
    looks_like_block_page,
)


class BlockedError(Exception):
    """Google 出現 CAPTCHA / 異常流量攔截時拋出,交給上層決定怎麼處理。"""


def search_google(
    driver,
    keyword: str,
    pages: int = 1,
    min_sleep: float = 2,
    max_sleep: float = 5,
) -> list[dict]:
    results = []

    for page in range(pages):
        start = page * 10
        url = f"https://www.google.com/search?q={quote_plus(keyword)}&start={start}&hl=zh-TW"
        driver.get(url)
        sleep_random(min_sleep, max_sleep)

        html = driver.page_source
        if looks_like_block_page(html):
            # 伺服器端無人可手動過驗證,直接回報,讓上層標記並繼續下一個關鍵字
            raise BlockedError(f"Google 攔截了關鍵字「{keyword}」第 {page + 1} 頁")

        # Google 搜尋結果 DOM 常變,所以用多種 selector 兼容
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
                    "div[data-sncf]",
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
