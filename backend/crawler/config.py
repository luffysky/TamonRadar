"""爬蟲設定。

原本是寫死的常數,現在改成 dataclass,讓前端每次請求可以帶不同關鍵字/頁數進來,
同時保留一組合理的預設值(舊的 CLI 行為)。
"""
import os
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


# 預設搜尋來源:有設 Brave/Serp 金鑰就優先用,否則退回 selenium(本機才建議)
def _default_provider() -> str:
    env = os.environ.get("SEARCH_PROVIDER")
    if env:
        return env
    # 預設先用 SerpAPI,沒有才用 Brave(實際執行時 serp 額度用完會自動 fallback 到 brave)
    if os.environ.get("SERPAPI_KEY"):
        return "serpapi"
    if os.environ.get("BRAVE_API_KEY"):
        return "brave"
    return "selenium"


VALID_PROVIDERS = ("brave", "serpapi", "serper", "googlecse", "tavily", "searxng", "duckduckgo", "selenium")

# 各領域對應的分類標籤(購物類沿用原本的計分分類器,其餘用領域當分類,避免全落「其他」)
VERTICAL_LABELS = {
    "food": "美食", "pet": "寵物", "animal": "動物/生態", "travel": "旅遊",
    "stock": "股市/投資", "startup": "創業", "realestate": "房地產", "job": "工作職缺",
    "course": "學習/課程", "health": "健康/醫療", "tech": "3C/科技", "car": "汽車", "secondhand": "二手",
    "ticket": "票券/活動", "rent": "租屋", "game": "遊戲/虛寶", "crypto": "加密貨幣",
    "flight": "機票/住宿", "clinic": "醫美/補教",
}


@dataclass
class CrawlConfig:
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    google_pages_per_keyword: int = 2
    max_detail_pages: int = 30
    min_sleep: float = 2.0
    max_sleep: float = 5.0
    headless: bool = True
    scrape_details: bool = True
    search_provider: str = field(default_factory=_default_provider)
    vertical: str = ""
    site_url: str = ""          # 整站爬起始網址(設了就走整站模式)
    site_max_pages: int = 30
    site_max_depth: int = 2
    output_dir: str = "output"

    def normalized(self) -> "CrawlConfig":
        """清掉空白關鍵字、夾住數值範圍,避免前端送來離譜的值。"""
        keywords = [k.strip() for k in self.keywords if k and k.strip()]
        if not keywords:
            keywords = list(DEFAULT_KEYWORDS)
        provider = self.search_provider if self.search_provider in VALID_PROVIDERS else _default_provider()
        return CrawlConfig(
            keywords=keywords,
            google_pages_per_keyword=max(1, min(self.google_pages_per_keyword, 20)),
            max_detail_pages=max(0, min(self.max_detail_pages, 100)),
            min_sleep=max(0.5, float(self.min_sleep)),
            max_sleep=max(float(self.min_sleep), float(self.max_sleep)),
            headless=self.headless,
            scrape_details=self.scrape_details,
            search_provider=provider,
            vertical=self.vertical,
            site_url=self.site_url,
            site_max_pages=self.site_max_pages,
            site_max_depth=self.site_max_depth,
            output_dir=self.output_dir,
        )
