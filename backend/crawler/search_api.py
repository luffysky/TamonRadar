"""搜尋 API 層:取代「用 Selenium 開 Google」的搜尋方式。

雲端 IP 直接爬 Google 很容易被擋驗證,改打搜尋 API 拿乾淨 JSON,穩定又快。
支援兩家,可切換:
  - brave    : Brave Search API(免費額度大)
  - serpapi  : SerpAPI(資料最豐富)
金鑰從環境變數讀:BRAVE_API_KEY / SERPAPI_KEY。
"""
import os
import time
from urllib.parse import urlparse

import requests

from .utils import clean_text, get_domain


class SearchApiError(Exception):
    """搜尋 API 呼叫失敗(沒金鑰、額度用完、網路錯誤等)。"""


# 所有「API 型」搜尋來源(非 selenium),fallback 嘗試順序
API_ORDER = ["serpapi", "brave", "searxng", "duckduckgo"]
API_PROVIDERS = set(API_ORDER)


def available_providers() -> dict[str, bool]:
    """回報每個 provider 是否可用,給前端顯示哪些可選。"""
    return {
        "serpapi": bool(os.environ.get("SERPAPI_KEY")),
        "brave": bool(os.environ.get("BRAVE_API_KEY")),
        "searxng": bool(os.environ.get("SEARXNG_URL")),
        "duckduckgo": True,   # 開源、免金鑰(雲端 IP 可能被限流)
        "selenium": True,     # 本機一定可用(雲端不建議)
    }


def _normalize(keyword: str, title: str, url: str, snippet: str, page: int) -> dict | None:
    title = clean_text(title)
    snippet = clean_text(snippet)
    if not title or not url or not url.startswith("http"):
        return None
    return {
        "keyword": keyword,
        "title": title,
        "url": url,
        "domain": get_domain(url),
        "snippet": snippet,
        "google_page": page,
    }


# Brave 免費版限每秒 1 次請求,用模組層時間戳節流避免 429
_brave_last_call = 0.0
_BRAVE_MIN_INTERVAL = 1.1


def _brave_throttle() -> None:
    global _brave_last_call
    wait = _BRAVE_MIN_INTERVAL - (time.monotonic() - _brave_last_call)
    if wait > 0:
        time.sleep(wait)
    _brave_last_call = time.monotonic()


def _search_brave(keyword: str, pages: int, api_key: str) -> list[dict]:
    results: list[dict] = []
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    for page in range(pages):
        params = {
            "q": keyword,
            "count": 20,
            "offset": page,          # Brave 用 offset 當分頁(0 起算)
            "country": "tw",
            "search_lang": "zh-hant",
        }
        _brave_throttle()
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers, params=params, timeout=20,
        )
        if resp.status_code == 401:
            raise SearchApiError("Brave API 金鑰無效或未授權(請確認已在 Brave 開通免費方案)")
        if resp.status_code == 429:
            raise SearchApiError("Brave 請求太頻繁(免費版限每秒 1 次),請稍後再試")
        resp.raise_for_status()
        web = (resp.json() or {}).get("web", {})
        for item in web.get("results", []):
            row = _normalize(
                keyword, item.get("title", ""), item.get("url", ""),
                item.get("description", ""), page + 1,
            )
            if row:
                results.append(row)
    return results


def _search_serpapi(keyword: str, pages: int, api_key: str) -> list[dict]:
    results: list[dict] = []
    for page in range(pages):
        params = {
            "engine": "google",
            "q": keyword,
            "start": page * 10,
            "num": 10,
            "hl": "zh-tw",
            "gl": "tw",
            "api_key": api_key,
        }
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
        if resp.status_code in (401, 403):
            raise SearchApiError("SerpAPI 金鑰無效或未設定")
        if resp.status_code == 429:
            raise SearchApiError("SerpAPI 額度已用完")
        resp.raise_for_status()
        data = resp.json() or {}
        if data.get("error"):
            raise SearchApiError(f"SerpAPI:{data['error']}")
        for item in data.get("organic_results", []):
            row = _normalize(
                keyword, item.get("title", ""), item.get("link", ""),
                item.get("snippet", ""), page + 1,
            )
            if row:
                results.append(row)
    return results


def _search_searxng(keyword: str, pages: int) -> list[dict]:
    base = os.environ.get("SEARXNG_URL")
    if not base:
        raise SearchApiError("未設定 SEARXNG_URL")
    results: list[dict] = []
    for page in range(pages):
        try:
            resp = requests.get(
                f"{base.rstrip('/')}/search",
                params={"q": keyword, "format": "json", "pageno": page + 1, "language": "zh-TW"},
                headers={"User-Agent": "TamonRadar"}, timeout=20,
            )
            resp.raise_for_status()
            data = resp.json() or {}
        except Exception as e:
            raise SearchApiError(f"SearXNG:{e}")
        for item in data.get("results", []):
            row = _normalize(keyword, item.get("title", ""), item.get("url", ""), item.get("content", ""), page + 1)
            if row:
                results.append(row)
    return results


def _search_duckduckgo(keyword: str, pages: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        raise SearchApiError("後端未安裝 ddgs 套件")
    results: list[dict] = []
    try:
        with DDGS() as d:
            for item in d.text(keyword, region="tw-tzh", max_results=pages * 10):
                row = _normalize(keyword, item.get("title", ""), item.get("href", ""), item.get("body", ""), 1)
                if row:
                    results.append(row)
    except Exception as e:
        raise SearchApiError(f"DuckDuckGo:{e}")
    return results


def resolve_order(primary: str) -> list[str]:
    """依偏好回傳實際可用的 API 嘗試順序(額度/失敗時自動 fallback)。"""
    avail = available_providers()
    order: list[str] = []
    if primary in API_ORDER:
        order.append(primary)
    for p in API_ORDER:
        if p not in order:
            order.append(p)
    return [p for p in order if avail.get(p)]


def search_api(provider: str, keyword: str, pages: int = 1) -> list[dict]:
    """用指定的搜尋 API 搜一個關鍵字。回傳與 search_google 相同的結構。"""
    if provider == "brave":
        key = os.environ.get("BRAVE_API_KEY")
        if not key:
            raise SearchApiError("未設定 BRAVE_API_KEY")
        return _search_brave(keyword, pages, key)
    if provider == "serpapi":
        key = os.environ.get("SERPAPI_KEY")
        if not key:
            raise SearchApiError("未設定 SERPAPI_KEY")
        return _search_serpapi(keyword, pages, key)
    if provider == "searxng":
        return _search_searxng(keyword, pages)
    if provider == "duckduckgo":
        return _search_duckduckgo(keyword, pages)
    raise SearchApiError(f"未知的搜尋 provider:{provider}")
