"""限流器:計數存在資料庫(tr_rate_limits),所有 Function 實例共用。

固定視窗,從第一次命中起算;資料庫暫時連不上時退回單一實例的記憶體計數(盡力而為)。
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


def _hit_memory(key: str, limit: int, window_seconds: int) -> bool:
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


def _hit_db(key: str, limit: int, window_seconds: int) -> bool:
    import db
    from sqlalchemy import case, or_

    now = time.time()
    t = db.RateLimitBucket.__table__
    stmt = db.dialect_insert(db.RateLimitBucket).values(key=key, hits=1, expires_at=now + window_seconds)
    expired = t.c.expires_at <= now
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_={
            "hits": case((expired, 1), else_=t.c.hits + 1),
            "expires_at": case((expired, stmt.excluded.expires_at), else_=t.c.expires_at),
        },
        # 超限時不更新,RETURNING 不會回傳任何列:超限的這次不計入
        where=or_(expired, t.c.hits < limit),
    ).returning(t.c.hits)
    with db.SessionLocal() as s:
        allowed = s.execute(stmt).first() is not None
        s.commit()
    return allowed


def hit(key: str, limit: int, window_seconds: float) -> bool:
    """記一次;回傳是否仍在限制內。超限的這次不計入。"""
    if limit <= 0:
        return False
    key = key[:255]
    try:
        return _hit_db(key, limit, window_seconds)
    except Exception as e:
        print(f"[ratelimit] 資料庫計數失敗,改用記憶體計數:{e}")
        return _hit_memory(key, limit, window_seconds)


def enforce(key: str, limit: int, window_seconds: int, message: str = "操作太頻繁,請稍後再試。") -> None:
    if not hit(key, limit, window_seconds):
        raise RateLimited(message)


def reset() -> None:
    """測試用:清空所有計數。"""
    with _lock:
        _hits.clear()
    try:
        import db
        from sqlalchemy import delete
        with db.SessionLocal() as s:
            s.execute(delete(db.RateLimitBucket))
            s.commit()
    except Exception:
        pass


def purge_expired() -> int:
    """清掉已過期的計數列(由定期清理工作呼叫)。"""
    import db
    from sqlalchemy import delete
    with db.SessionLocal() as s:
        n = s.execute(delete(db.RateLimitBucket).where(db.RateLimitBucket.expires_at <= time.time())).rowcount
        s.commit()
    return n
