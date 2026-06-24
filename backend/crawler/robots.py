"""遵守 robots.txt:抓取前檢查該網站是否允許。每個網域只抓一次 robots.txt(快取)。"""
import urllib.robotparser
from urllib.parse import urlparse

import requests

UA = "TamonRadarBot"
_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def _load(base: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(base + "/robots.txt", timeout=8, headers={"User-Agent": UA})
        if r.status_code >= 400 or not r.text.strip():
            rp.parse([])          # 沒有 robots.txt → 全部允許
        else:
            rp.parse(r.text.splitlines())
    except Exception:
        rp.parse([])              # 抓不到 robots.txt → 預設允許(不因此擋掉全部)
    return rp


def allowed(url: str) -> bool:
    """該網址是否允許抓取(依網站 robots.txt)。出錯預設允許。"""
    try:
        p = urlparse(url)
        if not p.scheme.startswith("http"):
            return True
        base = f"{p.scheme}://{p.netloc}"
        rp = _cache.get(base)
        if rp is None:
            rp = _load(base)
            _cache[base] = rp
        return rp.can_fetch(UA, url)
    except Exception:
        return True
