import random
import re
import time
from urllib.parse import urlparse, parse_qs, unquote


def sleep_random(min_seconds: float = 2, max_seconds: float = 5) -> None:
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
    """
    Google 搜尋結果有時會長得像 /url?q=https://example.com&sa=...
    這個函式會把真正網址抽出來。
    """
    if not url:
        return ""

    if url.startswith("/url?"):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "q" in query:
            return unquote(query["q"][0])

    return url


def looks_like_block_page(html: str) -> bool:
    """判斷是否為 Google 的 CAPTCHA / 異常流量攔截頁。

    修正:原本把單字 "sorry" 當關鍵字,正常頁面太常出現會誤判。
    改用較明確、攔截頁才會同時出現的片語,並要求多重訊號。
    """
    text = html.lower()

    strong_signals = [
        "unusual traffic",
        "our systems have detected unusual traffic",
        "/sorry/index",          # google sorry 頁的網址特徵
        "recaptcha",
        "g-recaptcha",
        "請證明您不是機器人",
        "我們的系統偵測到",
        "異常流量",
    ]
    if any(sig in text for sig in strong_signals):
        return True

    # 較弱的訊號需要兩個以上同時出現才算
    weak_signals = ["captcha", "verify you are a human", "not a robot", "驗證"]
    hits = sum(1 for sig in weak_signals if sig in text)
    return hits >= 2


# 價格:貨幣符號(或單位)必須緊貼數字,數字至少 1 位,允許千分位逗號。
# 修正:不再用裸 "$\s?[0-9,]+" 抓整頁雜訊,並過濾掉 0 與不合理小值。
_PRICE_PATTERNS = [
    (re.compile(r"NT\$\s?([0-9][0-9,]*)", re.I), "NT$"),
    (re.compile(r"TWD\s?([0-9][0-9,]*)", re.I), "TWD "),
    (re.compile(r"\$\s?([0-9][0-9,]*)"), "$"),
    (re.compile(r"¥\s?([0-9][0-9,]*)"), "¥"),
    (re.compile(r"JPY\s?([0-9][0-9,]*)", re.I), "JPY "),
    (re.compile(r"([0-9][0-9,]*)\s?円"), "", "円"),
    (re.compile(r"([0-9][0-9,]*)\s?日圓"), "", "日圓"),
    (re.compile(r"([0-9][0-9,]*)\s?元"), "", "元"),
]

# 低於這個值的多半是樓層/數量/運費雜訊,不是商品價
_MIN_REASONABLE_PRICE = 10


def _to_int(num_text: str) -> int:
    try:
        return int(num_text.replace(",", ""))
    except ValueError:
        return 0


def extract_price(text: str) -> str:
    """從文字中抓出最可能的商品價格。

    策略:蒐集所有候選價格,過濾掉 0 與過小的雜訊值,挑出現頻率最高
    (同一個價格在頁面重複出現,通常就是真正的售價)的那個。
    """
    if not text:
        return ""

    # display -> {count, pos(最早出現位置)}
    info: dict[str, dict] = {}

    for pattern_def in _PRICE_PATTERNS:
        pattern = pattern_def[0]
        prefix = pattern_def[1]
        suffix = pattern_def[2] if len(pattern_def) > 2 else ""

        for match in pattern.finditer(text):
            num_text = match.group(1)
            value = _to_int(num_text)
            if value < _MIN_REASONABLE_PRICE:
                continue
            display = f"{prefix}{num_text}{suffix}"
            if display not in info:
                info[display] = {"count": 0, "pos": match.start()}
            info[display]["count"] += 1
            info[display]["pos"] = min(info[display]["pos"], match.start())

    if not info:
        return ""

    # 選法:出現次數最多者優先(真正售價常重複出現);
    # 次數相同時取「最早出現」的,而不是最大值——避免被頁面其他大數字(如 30000)蓋過真正的 200。
    best = min(info.items(), key=lambda kv: (-kv[1]["count"], kv[1]["pos"]))
    return best[0]


# 分類關鍵字(可調權重:標題/摘要命中的份量比內文大,在 classify_item 處理)
_CATEGORY_KEYWORDS = {
    "周邊/商品": [
        "周邊", "公仔", "模型", "抱枕", "壓克力", "吊飾", "徽章", "立牌",
        "海報", "服飾", "預購", "再販", "figure", "goods", "預訂",
    ],
    "角色資訊": [
        "角色介紹", "角色", "聲優", "設定", "profile", "character", "wiki", "登場人物",
    ],
    "動畫/漫畫": [
        "動畫", "漫畫", "集數", "劇情", "anime", "manga", "第一季", "話數", "原作",
    ],
    "討論/心得": [
        "討論", "心得", "開箱", "評價", "review", "forum", "reddit", "ptt", "dcard", "巴哈",
    ],
    "購物頁": [
        "購買", "加入購物車", "結帳", "shop", "store", "cart", "賣場", "商品頁", "下單",
    ],
}


def classify_item(title: str, snippet: str, page_text: str) -> str:
    """計分制分類。

    修正:原本是 if 短路,只要命中 merch 關鍵字就回傳,導致幾乎全歸成周邊。
    改為每一類各自計分(標題/摘要權重 3,內文權重 1),取最高分;
    全 0 才回傳「其他」。
    """
    head = f"{title} {snippet}".lower()
    body = (page_text or "").lower()

    scores: dict[str, int] = {}
    for category, words in _CATEGORY_KEYWORDS.items():
        score = 0
        for word in words:
            w = word.lower()
            score += head.count(w) * 3
            score += body.count(w) * 1
        scores[category] = score

    best_category = max(scores, key=scores.get)
    if scores[best_category] == 0:
        return "其他"
    return best_category


def is_listing_url(url: str) -> bool:
    """判斷是否為「搜尋/列表頁」而非單一商品頁。

    這類頁面點進去是一整列商品,抓出的價格是混雜的(常出現亂價),
    所以不該顯示單一價格、也不該當成商品卡。
    """
    if not url:
        return False
    u = url.lower()
    markers = [
        "/search", "keyword=", "/find", "q=", "/category", "/categories",
        "/cat/", "/collections/", "list.php", "/mall/", "/shop/", "/store/",
        "/tag/", "/s?", "/sch/",
    ]
    return any(m in u for m in markers)


def is_valid_url(url: str, skip_extensions: tuple[str, ...]) -> bool:
    """修正:用網址 path 判斷副檔名,去掉 query string,避免 ...png?x=1 漏擋。"""
    if not url:
        return False
    if not url.startswith("http"):
        return False
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    if any(path.endswith(ext) for ext in skip_extensions):
        return False
    return True
