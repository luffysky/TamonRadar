"""搜尋 API 層:取代「用 Selenium 開 Google」的搜尋方式。

雲端 IP 直接爬 Google 很容易被擋驗證,改打搜尋 API 拿乾淨 JSON,穩定又快。
支援兩家,可切換:
  - brave    : Brave Search API(免費額度大)
  - serpapi  : SerpAPI(資料最豐富)
金鑰從環境變數讀:BRAVE_API_KEY / SERPAPI_KEY。
"""
import os
from urllib.parse import urlparse

import requests

from .utils import clean_text, get_domain


class SearchApiError(Exception):
    """搜尋 API 呼叫失敗(沒金鑰、額度用完、網路錯誤等)。"""


def available_providers() -> dict[str, bool]:
    """回報每個 provider 是否已設定金鑰,給前端顯示哪些可選。"""
    return {
        "brave": bool(os.environ.get("BRAVE_API_KEY")),
        "serpapi": bool(os.environ.get("SERPAPI_KEY")),
        "selenium": True,  # 本機一定可用(雲端不建議)
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
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers, params=params, timeout=20,
        )
        if resp.status_code == 401:
            raise SearchApiError("Brave API 金鑰無效或未設定")
        if resp.status_code == 429:
            raise SearchApiError("Brave API 額度已用完或太頻繁")
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
    raise SearchApiError(f"未知的搜尋 provider:{provider}")
