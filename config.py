# 搜尋設定

KEYWORDS = [
    "多聞 週邊",
    "多聞周邊",
    "多聞 公仔",
    "多聞 模型",
    "多聞 抱枕",
    "多聞 壓克力",
    "現在的是哪一個多聞",
    "多聞 角色介紹",
    "多聞 動畫",
    "多聞 漫畫",
]

# 每個關鍵字抓幾頁 Google 搜尋結果
GOOGLE_PAGES_PER_KEYWORD = 2

# 每頁 Google 搜尋結果約 10 筆
MAX_DETAIL_PAGES = 60

# 每次動作等待秒數，太快容易被擋
MIN_SLEEP = 2
MAX_SLEEP = 5

# Chrome 是否使用無頭模式
# 新手教學建議 False，比較能看到發生什麼事
HEADLESS = False

# 輸出資料夾
OUTPUT_DIR = "output"

# 請避免爬這些類型
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".zip", ".rar", ".7z", ".mp4", ".mp3"
)
