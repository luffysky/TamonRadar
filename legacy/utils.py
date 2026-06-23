import random
import re
import time
from urllib.parse import urlparse, parse_qs, unquote


def sleep_random(min_seconds: int = 2, max_seconds: int = 5) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def normalize_google_url(url: str) -> str:
    '''
    Google 搜尋結果有時會長得像 /url?q=https://example.com&sa=...
    這個函式會把真正網址抽出來。
    '''
    if not url:
        return ""

    if url.startswith("/url?"):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "q" in query:
            return unquote(query["q"][0])

    return url


def looks_like_block_page(html: str) -> bool:
    text = html.lower()
    block_words = [
        "unusual traffic",
        "our systems have detected",
        "captcha",
        "verify you are a human",
        "sorry",
    ]
    return any(word in text for word in block_words)


def extract_price(text: str) -> str:
    '''
    粗略抓價格：
    NT$1,280 / $1280 / ¥3,500 / 1,280円 / TWD 1200
    '''
    if not text:
        return ""

    patterns = [
        r"(NT\$\s?[0-9,]+)",
        r"(TWD\s?[0-9,]+)",
        r"(\$\s?[0-9,]+)",
        r"(¥\s?[0-9,]+)",
        r"([0-9,]+\s?円)",
        r"([0-9,]+\s?日圓)",
        r"([0-9,]+\s?元)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def classify_item(title: str, snippet: str, page_text: str) -> str:
    text = f"{title} {snippet} {page_text}".lower()

    merch_words = ["周邊", "商品", "公仔", "模型", "抱枕", "壓克力", "吊飾", "徽章", "立牌", "海報", "服飾", "購買", "預購", "shop", "store", "goods", "figure"]
    character_words = ["角色", "介紹", "聲優", "設定", "profile", "character", "wiki"]
    anime_words = ["動畫", "漫畫", "集數", "劇情", "anime", "manga"]
    discussion_words = ["討論", "心得", "開箱", "評價", "review", "forum", "reddit", "ptt", "dcard"]

    if any(word in text for word in merch_words):
        return "周邊/商品"
    if any(word in text for word in character_words):
        return "角色資訊"
    if any(word in text for word in anime_words):
        return "動畫/漫畫"
    if any(word in text for word in discussion_words):
        return "討論/心得"

    return "其他"


def is_valid_url(url: str, skip_extensions: tuple[str, ...]) -> bool:
    if not url:
        return False
    if not url.startswith("http"):
        return False
    lowered = url.lower()
    if any(lowered.endswith(ext) for ext in skip_extensions):
        return False
    return True
