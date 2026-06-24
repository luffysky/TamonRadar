"""遵守 robots.txt + 網域封鎖清單:抓取前檢查。每個網域只抓一次 robots.txt(快取)。"""
import os
import urllib.robotparser
from urllib.parse import urlparse

import requests

UA = "TamonRadarBot"
_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

# 預設封鎖:登入牆/服務條款明文禁止自動抓取的站(可用 BLOCKED_DOMAINS 增補)
_DEFAULT_BLOCK = {
    "facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com",
    "threads.net", "tiktok.com", "pinterest.com",
}
_BLOCK = _DEFAULT_BLOCK | {d.strip().lower() for d in os.environ.get("BLOCKED_DOMAINS", "").split(",") if d.strip()}


def blocked(url: str) -> bool:
    """是否在封鎖清單(登入牆/禁爬站)。"""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return any(host == d or host.endswith("." + d) for d in _BLOCK)
    except Exception:
        return False


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
