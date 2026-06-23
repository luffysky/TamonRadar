from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from utils import clean_text, extract_price, classify_item, sleep_random, looks_like_block_page


def scrape_detail_page(driver, item: dict, min_sleep: int = 2, max_sleep: int = 5) -> dict:
    url = item.get("url", "")

    detail = {
        "page_title": "",
        "meta_description": "",
        "h1": "",
        "price": "",
        "image_url": "",
        "key_info": "",
        "category": "",
        "status": "ok",
        "error": "",
    }

    try:
        driver.get(url)
        sleep_random(min_sleep, max_sleep)

        html = driver.page_source

        if looks_like_block_page(html):
            detail["status"] = "blocked_or_captcha"

        soup = BeautifulSoup(html, "lxml")

        if soup.title:
            detail["page_title"] = clean_text(soup.title.get_text())

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            detail["meta_description"] = clean_text(meta_desc.get("content"))

        h1 = soup.find("h1")
        if h1:
            detail["h1"] = clean_text(h1.get_text())

        # 圖片：優先 og:image，其次第一張圖片
        og_img = soup.find("meta", attrs={"property": "og:image"})
        if og_img and og_img.get("content"):
            detail["image_url"] = og_img.get("content")
        else:
            img = soup.find("img")
            if img and img.get("src"):
                detail["image_url"] = img.get("src")

        page_text = clean_text(soup.get_text(" ", strip=True))
        combined_text = " ".join([
            item.get("title", ""),
            item.get("snippet", ""),
            detail["page_title"],
            detail["meta_description"],
            detail["h1"],
            page_text[:3000],
        ])

        detail["price"] = extract_price(combined_text)
        detail["category"] = classify_item(
            item.get("title", ""),
            item.get("snippet", ""),
            page_text[:3000],
        )

        # 關鍵資訊不要塞爆 Excel，截前 300 字
        if detail["meta_description"]:
            detail["key_info"] = detail["meta_description"][:300]
        else:
            detail["key_info"] = page_text[:300]

    except Exception as e:
        detail["status"] = "error"
        detail["error"] = str(e)[:300]

    return {**item, **detail}
