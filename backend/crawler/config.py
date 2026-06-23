"""爬蟲設定。

原本是寫死的常數,現在改成 dataclass,讓前端每次請求可以帶不同關鍵字/頁數進來,
同時保留一組合理的預設值(舊的 CLI 行為)。
"""
from dataclasses import dataclass, field


# 預設關鍵字(前端沒帶關鍵字時使用)
DEFAULT_KEYWORDS = [
    "多聞 週邊",
    "多聞 公仔",
    "多聞 壓克力",
    "現在的是哪一個多聞",
    "多聞 角色介紹",
    "多聞 動畫",
]

# 請避免爬這些類型(用網址 path 判斷,不含 query string)
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".zip", ".rar", ".7z", ".mp4", ".mp3",
)


@dataclass
class CrawlConfig:
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    google_pages_per_keyword: int = 2
    max_detail_pages: int = 30
    min_sleep: float = 2.0
    max_sleep: float = 5.0
    headless: bool = True
    scrape_details: bool = True
    output_dir: str = "output"

    def normalized(self) -> "CrawlConfig":
        """清掉空白關鍵字、夾住數值範圍,避免前端送來離譜的值。"""
        keywords = [k.strip() for k in self.keywords if k and k.strip()]
        if not keywords:
            keywords = list(DEFAULT_KEYWORDS)
        return CrawlConfig(
            keywords=keywords,
            google_pages_per_keyword=max(1, min(self.google_pages_per_keyword, 5)),
            max_detail_pages=max(0, min(self.max_detail_pages, 100)),
            min_sleep=max(0.5, float(self.min_sleep)),
            max_sleep=max(float(self.min_sleep), float(self.max_sleep)),
            headless=self.headless,
            scrape_details=self.scrape_details,
            output_dir=self.output_dir,
        )
