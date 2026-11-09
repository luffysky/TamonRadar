"""單一入口的行程內限流器(滑動視窗)。

目前後端是單一行程,用記憶體就夠;重啟會歸零。之後要換 Redis 只需改這支。
"""
import threading
import time
from collections import deque

_MAX_KEYS = 50_000
_lock = threading.Lock()
_hits: dict[str, deque] = {}


class RateLimited(Exception):
    """超過限制;app 會統一轉成 HTTP 429。"""

    def __init__(self, message: str = "操作太頻繁,請稍後再試。"):
        super().__init__(message)
        self.message = message


def _prune(now: float) -> None:
    """key 太多時清掉已過期的,避免被隨機 key 撐爆記憶體。"""
    if len(_hits) < _MAX_KEYS:
        return
    for k in [k for k, q in _hits.items() if not q or q[-1][1] <= now]:
        del _hits[k]
    if len(_hits) >= _MAX_KEYS:
        for k in list(_hits)[: _MAX_KEYS // 10]:
            del _hits[k]


def hit(key: str, limit: int, window_seconds: int) -> bool:
    """記一次;回傳是否仍在限制內。超限的這次不計入。"""
    now = time.monotonic()
    with _lock:
        _prune(now)
        q = _hits.setdefault(key, deque())
        while q and q[0][1] <= now:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append((now, now + window_seconds))
        return True


def enforce(key: str, limit: int, window_seconds: int, message: str = "操作太頻繁,請稍後再試。") -> None:
    if not hit(key, limit, window_seconds):
        raise RateLimited(message)


def reset() -> None:
    """測試用:清空所有計數。"""
    with _lock:
        _hits.clear()
