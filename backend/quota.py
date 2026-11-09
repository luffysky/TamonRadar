"""額度與用量上限的集中入口:每日額度、AI 花費閘門、爬蟲/排程/監看上限。

管理員、特權與付費方案(plan != free)維持不受每日額度限制,上限也用較寬的一組。
"""
import os
from dataclasses import dataclass

import auth
import db
import ratelimit


class QuotaExceeded(ratelimit.RateLimited):
    """額度或上限用完;app 會統一轉成 HTTP 429。"""


# ---------- 每日額度 ----------

def is_unlimited(user) -> bool:
    return bool(getattr(user, "privileged", False)) or getattr(user, "plan", "free") != "free" or auth.is_admin(user)


def daily_limit(kind: str) -> int:
    return int(os.environ.get("FREE_AI_DAILY", "30") if kind == "ai" else os.environ.get("FREE_SEARCH_DAILY", "15"))


def enforce(user, kind: str) -> None:
    """免費使用者的每日額度;特權或付費方案不受限。"""
    if is_unlimited(user):
        return
    limit = daily_limit(kind)
    ok, _used = db.quota_use(user.id, kind, limit)
    if not ok:
        raise QuotaExceeded(f"今日免費{'AI' if kind == 'ai' else '搜尋'}額度已用完(每日 {limit} 次)。升級方案或明天再來。")


def _load_user(user_id: int):
    with db.SessionLocal() as s:
        user = s.get(db.User, user_id)
    if user is None or user.banned:
        raise QuotaExceeded("此帳號無法使用這項功能。")
    return user


def enforce_by_id(user_id: int, kind: str) -> None:
    enforce(_load_user(user_id), kind)


# ---------- AI 閘門(由 ai.py 在實際呼叫模型前統一呼叫,所有入口都會經過)----------

AI_PER_MINUTE = int(os.environ.get("FREE_AI_PER_MINUTE", "10"))
BOT_AI_PER_HOUR = int(os.environ.get("BOT_AI_PER_HOUR", "20"))
BOT_AI_DAILY = int(os.environ.get("BOT_AI_DAILY", "300"))
FREE_IMAGE_DAILY = int(os.environ.get("FREE_IMAGE_DAILY", "3"))


def gate_ai(user_id: int | None, actor: str = "") -> None:
    """每次 AI 呼叫前的檢查。沒有登入身分也沒有 bot actor 一律拒絕,避免匿名花共用金鑰。"""
    if user_id:
        user = _load_user(user_id)
        if not is_unlimited(user):
            ratelimit.enforce(f"ai:user:{user_id}", AI_PER_MINUTE, 60, "AI 使用太頻繁,請稍後再試。")
        enforce(user, "ai")
        return
    if actor:
        ratelimit.enforce(f"ai:bot:{actor}", BOT_AI_PER_HOUR, 3600, "你問得有點快,請稍後再試 🙏")
        ratelimit.enforce("ai:bot:global", BOT_AI_DAILY, 86400, "今日機器人額度已用完,明天再來或到網站使用。")
        return
    raise QuotaExceeded("AI 功能需要登入後才能使用。")


def gate_image(user_id: int | None) -> None:
    """圖片生成比文字貴很多:另外限制免費使用者每日張數,同時計入 AI 額度。"""
    if not user_id:
        raise QuotaExceeded("AI 功能需要登入後才能使用。")
    user = _load_user(user_id)
    if not is_unlimited(user):
        ratelimit.enforce(f"ai:image:{user_id}", FREE_IMAGE_DAILY, 86400, f"今日免費封面生成已用完(每日 {FREE_IMAGE_DAILY} 張)。")
    enforce(user, "ai")


# ---------- 爬蟲 / 排程 / 監看上限 ----------

@dataclass(frozen=True)
class Caps:
    keywords: int            # 每次搜尋的關鍵字數
    pages: int               # 每個關鍵字的搜尋頁數
    detail_pages: int        # 進詳細頁的數量
    site_pages: int          # 整站爬頁數
    site_depth: int          # 整站爬深度
    schedules: int           # 排程數
    watches: int             # 監看數
    favorite_targets: int    # 有設目標價的收藏數
    concurrent_jobs: int     # 同時進行中的爬蟲任務數
    min_schedule_hours: int  # 排程最短間隔(小時)
    min_watch_minutes: int   # 監看最短間隔(分鐘)


FREE_CAPS = Caps(
    keywords=6, pages=3, detail_pages=20, site_pages=100, site_depth=3,
    schedules=3, watches=10, favorite_targets=10, concurrent_jobs=1,
    min_schedule_hours=6, min_watch_minutes=5,
)


def _unlimited_caps() -> Caps:
    return Caps(
        keywords=20, pages=20, detail_pages=100,
        site_pages=int(os.environ.get("SITE_MAX_PAGES_CAP", "5000")), site_depth=12,
        schedules=20, watches=100, favorite_targets=100, concurrent_jobs=2,
        min_schedule_hours=1, min_watch_minutes=1,
    )


def caps_for(user) -> Caps:
    return _unlimited_caps() if is_unlimited(user) else FREE_CAPS


def caps_for_id(user_id: int) -> Caps:
    """排程器用(手上只有 user_id);使用者不存在時用最嚴的一組。"""
    with db.SessionLocal() as s:
        user = s.get(db.User, user_id)
    return caps_for(user) if user is not None else FREE_CAPS
