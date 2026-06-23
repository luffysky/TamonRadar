"""角色標記:從標題/摘要判斷是《現在的是哪一個多聞!?》裡的哪位角色。

規則式(不需 AI):比對角色全名與常見簡稱。"多聞" 本身是作品名,不單獨當判斷依據。
"""

# 順序有意義:先比對較具體的全名
_CHARACTERS: list[tuple[str, list[str]]] = [
    ("福原多聞", ["福原多聞", "福原"]),
    ("坂口櫻利", ["坂口櫻利", "櫻利", "桜利"]),
    ("橘敬人", ["橘敬人", "敬人"]),
    ("石橋夏木", ["石橋夏木", "夏木"]),
    ("甲斐倫太郎", ["甲斐倫太郎", "倫太郎"]),
    ("歌夏", ["歌夏"]),
]


def detect_character(*texts: str) -> str:
    """回傳偵測到的角色全名;沒有就回空字串。"""
    blob = " ".join(t for t in texts if t)
    for name, aliases in _CHARACTERS:
        if any(alias in blob for alias in aliases):
            return name
    return ""
