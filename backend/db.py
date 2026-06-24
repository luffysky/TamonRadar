"""資料庫層(SQLAlchemy)。

- 設了 DATABASE_URL(Supabase / Postgres)就連雲端資料庫。
- 沒設就退回本機 SQLite 檔(方便本機開發,不用裝 Postgres)。
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import crypto
import money

from sqlalchemy import (
    JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, create_engine, func, inspect, select, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker,
)


def _build_url() -> tuple[str, dict]:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Supabase / 一般 Postgres 給的是 postgresql://,SQLAlchemy 要用 psycopg 驅動
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]

        if url.startswith("postgresql+psycopg://"):
            return url, {}
        if url.startswith("sqlite://"):
            return url, {"check_same_thread": False}

        # 格式不對(例如有人填了 https://...)→ 不要讓整個 app 在 import 就崩潰,
        # 退回本機 SQLite 並印出明確警告,方便排查。
        print(
            f"[db] ⚠️ DATABASE_URL 格式不正確,必須是 postgresql://使用者:密碼@主機:5432/資料庫。"
            f"收到的開頭是「{url[:15]}…」。暫時改用本機 SQLite(資料不會保留)。"
        )

    Path("data").mkdir(exist_ok=True)
    return "sqlite:///./data/tamonradar.db", {"check_same_thread": False}


_url, _connect_args = _build_url()
engine = create_engine(_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

IS_SQLITE = _url.startswith("sqlite")


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "tr_users"  # 加 tr_ 前綴,避開 Supabase 內建的 users 表

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(60), default="")        # 顯示名稱
    password_hash: Mapped[str] = mapped_column(String(255), default="")  # OAuth 使用者為空
    provider: Mapped[str] = mapped_column(String(32), default="local")   # local | google
    plan: Mapped[str] = mapped_column(String(20), default="free")        # free | pro
    privileged: Mapped[bool] = mapped_column(default=False)              # 特權:全功能/全 AI 免費、跳過所有額度
    banned: Mapped[bool] = mapped_column(default=False)                  # 停權:無法登入/使用
    email_verified: Mapped[bool] = mapped_column(default=False)          # Email 是否已驗證
    ai_used: Mapped[int] = mapped_column(default=0)                      # AI 累計呼叫次數
    admin_note: Mapped[str] = mapped_column(Text, default="")           # 後台備註(CRM)
    tags: Mapped[list] = mapped_column(JSON, default=list)              # 後台標籤(CRM)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    runs: Mapped[list["Run"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "tr_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="done")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    records: Mapped[list] = mapped_column(JSON, default=list)
    shared: Mapped[bool] = mapped_column(default=False)

    user: Mapped["User"] = relationship(back_populates="runs")


class Settings(Base):
    __tablename__ = "tr_user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), primary_key=True)
    discord_webhook: Mapped[str] = mapped_column(String(500), default="")
    telegram_token: Mapped[str] = mapped_column(String(200), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(100), default="")
    # 使用者自備的 AI 金鑰(BYO);留空則用後端共用金鑰
    openai_key: Mapped[str] = mapped_column(String(255), default="")
    anthropic_key: Mapped[str] = mapped_column(String(255), default="")
    gemini_key: Mapped[str] = mapped_column(String(255), default="")
    groq_key: Mapped[str] = mapped_column(String(255), default="")
    openrouter_key: Mapped[str] = mapped_column(String(255), default="")
    ai_provider: Mapped[str] = mapped_column(String(20), default="")  # ""=自動 / openai / gemini / groq / openrouter / anthropic
    daily_digest: Mapped[bool] = mapped_column(default=False)  # 每日彙整通知


class Schedule(Base):
    __tablename__ = "tr_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), index=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(32), default="brave")
    pages: Mapped[int] = mapped_column(default=2)
    max_detail: Mapped[int] = mapped_column(default=0)
    scrape_details: Mapped[bool] = mapped_column(default=False)
    interval_hours: Mapped[int] = mapped_column(default=24)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Watch(Base):
    __tablename__ = "tr_watches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(1000))
    available_keywords: Mapped[list] = mapped_column(JSON, default=list)
    unavailable_keywords: Mapped[list] = mapped_column(JSON, default=list)
    interval_minutes: Mapped[int] = mapped_column(default=5)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_status: Mapped[str] = mapped_column(String(20), default="unknown")  # unknown|available|unavailable
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_price: Mapped[int | None] = mapped_column(nullable=True)      # 低於此台幣價就通知
    last_price_twd: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Post(Base):
    __tablename__ = "tr_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    excerpt: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")          # Markdown
    cover_image: Mapped[str] = mapped_column(String(1000), default="")
    category: Mapped[str] = mapped_column(String(50), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    published: Mapped[bool] = mapped_column(default=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Thread(Base):
    __tablename__ = "tr_threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), index=True)
    author_email: Mapped[str] = mapped_column(String(255), default="")
    reply_count: Mapped[int] = mapped_column(default=0)
    likes: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_reply_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Reply(Base):
    __tablename__ = "tr_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("tr_threads.id"), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"))
    author_email: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Favorite(Base):
    __tablename__ = "tr_favorites"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_fav_user_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(300), default="")
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    domain: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[str] = mapped_column(String(50), default="")
    target_twd: Mapped[int | None] = mapped_column(nullable=True)  # 目標價(台幣),低於就通知
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    __tablename__ = "tr_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(80), default="")
    target: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Announcement(Base):
    __tablename__ = "tr_announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(20), default="info")  # info|warning|success
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Report(Base):
    __tablename__ = "tr_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(20), default="")  # thread|reply|post
    target_id: Mapped[int] = mapped_column(default=0)
    reason: Mapped[str] = mapped_column(String(500), default="")
    reporter_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|resolved
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AppSetting(Base):
    __tablename__ = "tr_app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Usage(Base):
    __tablename__ = "tr_usage"
    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    ai: Mapped[int] = mapped_column(default=0)
    search: Mapped[int] = mapped_column(default=0)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """相容既有資料庫:補上後來新增的欄位(create_all 不會改既有表)。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "tr_users" in tables:
        cols = {c["name"] for c in insp.get_columns("tr_users")}
        for col, ddl in (
            ("provider", "ALTER TABLE tr_users ADD COLUMN provider VARCHAR(32) DEFAULT 'local'"),
            ("plan", "ALTER TABLE tr_users ADD COLUMN plan VARCHAR(20) DEFAULT 'free'"),
            ("ai_used", "ALTER TABLE tr_users ADD COLUMN ai_used INTEGER DEFAULT 0"),
            ("admin_note", "ALTER TABLE tr_users ADD COLUMN admin_note TEXT DEFAULT ''"),
            ("tags", "ALTER TABLE tr_users ADD COLUMN tags JSON"),
            ("username", "ALTER TABLE tr_users ADD COLUMN username VARCHAR(60) DEFAULT ''"),
            ("privileged", "ALTER TABLE tr_users ADD COLUMN privileged BOOLEAN DEFAULT false"),
            ("banned", "ALTER TABLE tr_users ADD COLUMN banned BOOLEAN DEFAULT false"),
            ("email_verified", "ALTER TABLE tr_users ADD COLUMN email_verified BOOLEAN DEFAULT false"),
        ):
            if col not in cols:
                with engine.begin() as conn:
                    conn.execute(text(ddl))

    if "tr_threads" in tables:
        cols = {c["name"] for c in insp.get_columns("tr_threads")}
        if "likes" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tr_threads ADD COLUMN likes INTEGER DEFAULT 0"))

    if "tr_runs" in tables:
        cols = {c["name"] for c in insp.get_columns("tr_runs")}
        if "shared" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tr_runs ADD COLUMN shared BOOLEAN DEFAULT false"))

    if "tr_watches" in tables:
        cols = {c["name"] for c in insp.get_columns("tr_watches")}
        for col, ddl in (
            ("target_price", "ALTER TABLE tr_watches ADD COLUMN target_price INTEGER"),
            ("last_price_twd", "ALTER TABLE tr_watches ADD COLUMN last_price_twd INTEGER"),
        ):
            if col not in cols:
                with engine.begin() as conn:
                    conn.execute(text(ddl))

    if "tr_user_settings" in tables:
        cols = {c["name"] for c in insp.get_columns("tr_user_settings")}
        for col, ddl in (
            ("openai_key", "ALTER TABLE tr_user_settings ADD COLUMN openai_key VARCHAR(255) DEFAULT ''"),
            ("anthropic_key", "ALTER TABLE tr_user_settings ADD COLUMN anthropic_key VARCHAR(255) DEFAULT ''"),
            ("gemini_key", "ALTER TABLE tr_user_settings ADD COLUMN gemini_key VARCHAR(255) DEFAULT ''"),
            ("groq_key", "ALTER TABLE tr_user_settings ADD COLUMN groq_key VARCHAR(255) DEFAULT ''"),
            ("openrouter_key", "ALTER TABLE tr_user_settings ADD COLUMN openrouter_key VARCHAR(255) DEFAULT ''"),
            ("ai_provider", "ALTER TABLE tr_user_settings ADD COLUMN ai_provider VARCHAR(20) DEFAULT ''"),
            ("daily_digest", "ALTER TABLE tr_user_settings ADD COLUMN daily_digest BOOLEAN DEFAULT false"),
        ):
            if col not in cols:
                with engine.begin() as conn:
                    conn.execute(text(ddl))


# ---------- Run 持久化 ----------

def save_run(job, user_id: int) -> None:
    result = job.result or {"records": [], "summary": {}}
    with SessionLocal() as s:
        run = s.get(Run, job.id)
        if run is None:
            run = Run(id=job.id, user_id=user_id)
            s.add(run)
        run.user_id = user_id
        run.status = job.status
        run.finished_at = _now()
        run.keywords = list(job.config.keywords)
        run.summary = result.get("summary", {})
        run.records = result.get("records", [])
        s.commit()


def list_runs(user_id: int) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(
            select(Run).where(Run.user_id == user_id).order_by(Run.finished_at.desc())
        ).all()
        return [{
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "keywords": r.keywords or [],
            "summary": r.summary or {},
        } for r in rows]


def previous_run(user_id: int, before_iso: str, exclude_id: str) -> dict | None:
    """同一使用者、比指定時間更早完成的最近一次成功爬蟲(給價格雷達比較用)。"""
    with SessionLocal() as s:
        rows = s.scalars(
            select(Run)
            .where(Run.user_id == user_id, Run.id != exclude_id, Run.status == "done")
            .order_by(Run.finished_at.desc())
        ).all()
        for r in rows:
            iso = r.finished_at.isoformat() if r.finished_at else ""
            if iso < before_iso:
                return {
                    "id": r.id,
                    "finished_at": iso,
                    "keywords": r.keywords or [],
                    "records": r.records or [],
                }
    return None


def get_run(run_id: str, user_id: int | None = None) -> dict | None:
    with SessionLocal() as s:
        run = s.get(Run, run_id)
        if run is None:
            return None
        if user_id is not None and run.user_id != user_id:
            return None
        return {
            "id": run.id,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "status": run.status,
            "keywords": run.keywords or [],
            "summary": run.summary or {},
            "records": run.records or [],
            "shared": bool(run.shared),
        }


def set_run_shared(run_id: str, user_id: int, shared: bool) -> bool:
    with SessionLocal() as s:
        run = s.get(Run, run_id)
        if run is None or run.user_id != user_id:
            return False
        run.shared = bool(shared)
        s.commit()
        return True


def get_shared_run(run_id: str) -> dict | None:
    """公開分享用:只有被標記 shared 的才回傳。"""
    with SessionLocal() as s:
        run = s.get(Run, run_id)
        if run is None or not run.shared:
            return None
        return {
            "id": run.id,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "keywords": run.keywords or [],
            "summary": run.summary or {},
            "records": run.records or [],
        }


def create_run_record(user_id: int, run_id: str, keywords: list, result: dict) -> None:
    """給排程的爬蟲用:直接寫入一筆 Run(不經過記憶體 job)。"""
    with SessionLocal() as s:
        run = Run(
            id=run_id, user_id=user_id, status="done",
            keywords=list(keywords),
            summary=result.get("summary", {}),
            records=result.get("records", []),
        )
        s.add(run)
        s.commit()


# ---------- 通知設定 ----------

def get_settings(user_id: int) -> dict:
    fields = ("discord_webhook", "telegram_token", "telegram_chat_id",
              "openai_key", "anthropic_key", "gemini_key", "groq_key", "openrouter_key", "ai_provider")
    with SessionLocal() as s:
        st = s.get(Settings, user_id)
        if st is None:
            return {**{k: "" for k in fields}, "daily_digest": False}
        out = {
            k: (crypto.decrypt(getattr(st, k)) if k in _SECRET_FIELDS else (getattr(st, k) or ""))
            for k in fields
        }
        out["daily_digest"] = bool(st.daily_digest)
        return out


# 需要加密儲存的敏感欄位
_SECRET_FIELDS = {
    "discord_webhook", "telegram_token", "telegram_chat_id",
    "openai_key", "anthropic_key", "gemini_key", "groq_key", "openrouter_key",
}


def save_settings(user_id: int, data: dict) -> None:
    fields = ("discord_webhook", "telegram_token", "telegram_chat_id",
              "openai_key", "anthropic_key", "gemini_key", "groq_key", "openrouter_key", "ai_provider")
    with SessionLocal() as s:
        st = s.get(Settings, user_id)
        if st is None:
            st = Settings(user_id=user_id)
            s.add(st)
        for key in fields:
            if key in data and data[key] is not None:
                value = crypto.encrypt(data[key]) if key in _SECRET_FIELDS else data[key]
                setattr(st, key, value)
        if "daily_digest" in data and data["daily_digest"] is not None:
            st.daily_digest = bool(data["daily_digest"])
        s.commit()


def list_digest_user_ids() -> list[int]:
    with SessionLocal() as s:
        return [uid for (uid,) in s.execute(
            select(Settings.user_id).where(Settings.daily_digest == True)).all()]  # noqa: E712


# ---------- 排程 ----------

def _schedule_dict(sc: "Schedule") -> dict:
    return {
        "id": sc.id,
        "user_id": sc.user_id,
        "keywords": sc.keywords or [],
        "provider": sc.provider,
        "pages": sc.pages,
        "max_detail": sc.max_detail,
        "scrape_details": sc.scrape_details,
        "interval_hours": sc.interval_hours,
        "enabled": sc.enabled,
        "last_run": sc.last_run.isoformat() if sc.last_run else None,
    }


def list_schedules(user_id: int) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Schedule).where(Schedule.user_id == user_id).order_by(Schedule.id.desc())).all()
        return [_schedule_dict(r) for r in rows]


def list_enabled_schedules() -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Schedule).where(Schedule.enabled == True)).all()  # noqa: E712
        return [_schedule_dict(r) for r in rows]


def get_schedule(schedule_id: int, user_id: int | None = None) -> dict | None:
    with SessionLocal() as s:
        sc = s.get(Schedule, schedule_id)
        if sc is None or (user_id is not None and sc.user_id != user_id):
            return None
        return _schedule_dict(sc)


def create_schedule(user_id: int, data: dict) -> dict:
    with SessionLocal() as s:
        sc = Schedule(
            user_id=user_id,
            keywords=data.get("keywords", []),
            provider=data.get("provider", "brave"),
            pages=data.get("pages", 2),
            max_detail=data.get("max_detail", 0),
            scrape_details=data.get("scrape_details", False),
            interval_hours=data.get("interval_hours", 24),
            enabled=data.get("enabled", True),
        )
        s.add(sc)
        s.commit()
        s.refresh(sc)
        return _schedule_dict(sc)


def update_schedule(schedule_id: int, user_id: int, data: dict) -> dict | None:
    with SessionLocal() as s:
        sc = s.get(Schedule, schedule_id)
        if sc is None or sc.user_id != user_id:
            return None
        for key in ("keywords", "provider", "pages", "max_detail", "scrape_details", "interval_hours", "enabled"):
            if key in data and data[key] is not None:
                setattr(sc, key, data[key])
        s.commit()
        s.refresh(sc)
        return _schedule_dict(sc)


def touch_schedule(schedule_id: int) -> None:
    with SessionLocal() as s:
        sc = s.get(Schedule, schedule_id)
        if sc:
            sc.last_run = _now()
            s.commit()


def delete_schedule(schedule_id: int, user_id: int) -> bool:
    with SessionLocal() as s:
        sc = s.get(Schedule, schedule_id)
        if sc is None or sc.user_id != user_id:
            return False
        s.delete(sc)
        s.commit()
        return True


# ---------- 監看(到貨/開賣通知)----------

def _watch_dict(w: "Watch") -> dict:
    return {
        "id": w.id,
        "user_id": w.user_id,
        "name": w.name,
        "url": w.url,
        "available_keywords": w.available_keywords or [],
        "unavailable_keywords": w.unavailable_keywords or [],
        "interval_minutes": w.interval_minutes,
        "enabled": w.enabled,
        "last_status": w.last_status,
        "last_checked": w.last_checked.isoformat() if w.last_checked else None,
        "target_price": w.target_price,
        "last_price_twd": w.last_price_twd,
    }


def list_watches(user_id: int) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Watch).where(Watch.user_id == user_id).order_by(Watch.id.desc())).all()
        return [_watch_dict(w) for w in rows]


def list_enabled_watches() -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Watch).where(Watch.enabled == True)).all()  # noqa: E712
        return [_watch_dict(w) for w in rows]


def get_watch(watch_id: int, user_id: int | None = None) -> dict | None:
    with SessionLocal() as s:
        w = s.get(Watch, watch_id)
        if w is None or (user_id is not None and w.user_id != user_id):
            return None
        return _watch_dict(w)


def create_watch(user_id: int, data: dict) -> dict:
    with SessionLocal() as s:
        w = Watch(
            user_id=user_id,
            name=data.get("name", "")[:200],
            url=data.get("url", ""),
            available_keywords=data.get("available_keywords", []),
            unavailable_keywords=data.get("unavailable_keywords", []),
            interval_minutes=max(1, min(int(data.get("interval_minutes", 5)), 1440)),
            enabled=data.get("enabled", True),
            target_price=data.get("target_price"),
        )
        s.add(w)
        s.commit()
        s.refresh(w)
        return _watch_dict(w)


def update_watch(watch_id: int, user_id: int, data: dict) -> dict | None:
    with SessionLocal() as s:
        w = s.get(Watch, watch_id)
        if w is None or w.user_id != user_id:
            return None
        for key in ("name", "url", "available_keywords", "unavailable_keywords", "interval_minutes", "enabled", "target_price"):
            if key in data:
                setattr(w, key, data[key])
        s.commit()
        s.refresh(w)
        return _watch_dict(w)


def set_watch_status(watch_id: int, status: str, price_twd: int | None = None) -> None:
    with SessionLocal() as s:
        w = s.get(Watch, watch_id)
        if w:
            w.last_status = status
            w.last_checked = _now()
            if price_twd is not None:
                w.last_price_twd = price_twd
            s.commit()


def delete_watch(watch_id: int, user_id: int) -> bool:
    with SessionLocal() as s:
        w = s.get(Watch, watch_id)
        if w is None or w.user_id != user_id:
            return False
        s.delete(w)
        s.commit()
        return True


# ---------- 使用量 / 管理員 ----------

def delete_user(user_id: int) -> bool:
    """刪除使用者與其所有資料。"""
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u is None:
            return False
        for model, col in (
            (Favorite, Favorite.user_id), (Watch, Watch.user_id), (Schedule, Schedule.user_id),
            (Run, Run.user_id), (Settings, Settings.user_id), (Post, Post.author_id),
            (Reply, Reply.author_id), (Thread, Thread.author_id),
        ):
            for row in s.scalars(select(model).where(col == user_id)).all():
                s.delete(row)
        s.delete(u)
        s.commit()
        return True


def change_password(user_id: int, new_hash: str) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u is None:
            return False
        u.password_hash = new_hash
        s.commit()
        return True


def bump_ai_usage(user_id: int) -> None:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if u:
            u.ai_used = (u.ai_used or 0) + 1
            s.commit()


def set_user_plan(user_id: int, plan: str) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        u.plan = plan
        s.commit()
        return True


def admin_stats() -> dict:
    from datetime import timedelta
    week_ago = _now() - timedelta(days=7)
    with SessionLocal() as s:
        total_users = s.scalar(select(func.count()).select_from(User)) or 0
        total_ai = s.scalar(select(func.coalesce(func.sum(User.ai_used), 0))) or 0
        total_runs = s.scalar(select(func.count()).select_from(Run)) or 0
        total_watches = s.scalar(select(func.count()).select_from(Watch)) or 0
        total_schedules = s.scalar(select(func.count()).select_from(Schedule)) or 0
        total_posts = s.scalar(select(func.count()).select_from(Post)) or 0
        total_threads = s.scalar(select(func.count()).select_from(Thread)) or 0
        total_replies = s.scalar(select(func.count()).select_from(Reply)) or 0
        new_users_7d = s.scalar(select(func.count()).select_from(User).where(User.created_at >= week_ago)) or 0
        by_provider = {str(k): int(v) for k, v in s.execute(
            select(User.provider, func.count()).group_by(User.provider)).all()}
        by_plan = {str(k): int(v) for k, v in s.execute(
            select(User.plan, func.count()).group_by(User.plan)).all()}
        top_ai = [{"email": e, "ai_used": int(n)} for e, n in s.execute(
            select(User.email, User.ai_used).order_by(User.ai_used.desc()).limit(5)).all() if n]
    return {
        "total_users": int(total_users),
        "total_ai_calls": int(total_ai),
        "total_runs": int(total_runs),
        "total_watches": int(total_watches),
        "total_schedules": int(total_schedules),
        "total_posts": int(total_posts),
        "total_threads": int(total_threads),
        "total_replies": int(total_replies),
        "new_users_7d": int(new_users_7d),
        "by_provider": by_provider,
        "by_plan": by_plan,
        "top_ai_users": top_ai,
    }


def admin_users(limit: int = 500) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all()
        return [{
            "id": u.id,
            "email": u.email,
            "username": u.username or "",
            "provider": u.provider,
            "plan": u.plan,
            "privileged": bool(u.privileged),
            "ai_used": u.ai_used or 0,
            "tags": u.tags or [],
            "created_at": u.created_at.isoformat() if u.created_at else None,
        } for u in rows]


def get_user_detail(user_id: int) -> dict | None:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return None
        runs = s.scalar(select(func.count()).select_from(Run).where(Run.user_id == user_id)) or 0
        watches = s.scalar(select(func.count()).select_from(Watch).where(Watch.user_id == user_id)) or 0
        schedules = s.scalar(select(func.count()).select_from(Schedule).where(Schedule.user_id == user_id)) or 0
        threads = s.scalar(select(func.count()).select_from(Thread).where(Thread.author_id == user_id)) or 0
        favorites = s.scalar(select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)) or 0
        posts = s.scalar(select(func.count()).select_from(Post).where(Post.author_id == user_id)) or 0
        replies = s.scalar(select(func.count()).select_from(Reply).where(Reply.author_id == user_id)) or 0
        # 最近搜尋紀錄
        recent_rows = s.scalars(select(Run).where(Run.user_id == user_id).order_by(Run.finished_at.desc()).limit(10)).all()
        recent_runs = [{
            "id": r.id, "keywords": r.keywords or [],
            "total": (r.summary or {}).get("total", 0) if isinstance(r.summary, dict) else 0,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        } for r in recent_rows]
        st = s.get(Settings, user_id)
        channels = {
            "discord": bool(st and st.discord_webhook),
            "telegram": bool(st and st.telegram_token and st.telegram_chat_id),
            "own_ai_keys": bool(st and (st.openai_key or st.anthropic_key or st.gemini_key or st.groq_key or st.openrouter_key)),
            "daily_digest": bool(st and st.daily_digest),
        }
        return {
            "id": u.id, "email": u.email, "username": u.username or "", "provider": u.provider, "plan": u.plan,
            "privileged": bool(u.privileged), "banned": bool(u.banned),
            "ai_used": u.ai_used or 0, "admin_note": u.admin_note or "", "tags": u.tags or [],
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "counts": {"runs": int(runs), "watches": int(watches), "schedules": int(schedules),
                       "threads": int(threads), "favorites": int(favorites), "posts": int(posts), "replies": int(replies)},
            "recent_runs": recent_runs,
            "channels": channels,
        }


def mark_email_verified(user_id: int) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        u.email_verified = True
        s.commit()
        return True


def set_banned(user_id: int, banned: bool) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        u.banned = bool(banned)
        s.commit()
        return True


def is_banned(user_id: int) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        return bool(u and u.banned)


def all_users_for_export() -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(User).order_by(User.created_at.asc())).all()
        return [{
            "id": u.id, "email": u.email, "username": u.username or "", "provider": u.provider,
            "plan": u.plan, "privileged": bool(u.privileged), "banned": bool(u.banned),
            "ai_used": u.ai_used or 0, "tags": ";".join(u.tags or []),
            "created_at": u.created_at.isoformat() if u.created_at else "",
        } for u in rows]


def all_user_emails() -> list[str]:
    with SessionLocal() as s:
        return [e for (e,) in s.execute(
            select(User.email).where(User.banned == False, User.email != "")).all()]  # noqa: E712


# ---------- 稽核日誌 ----------
def log_audit(admin_email: str, action: str, target: str = "", detail: str = "") -> None:
    try:
        with SessionLocal() as s:
            s.add(AuditLog(admin_email=admin_email, action=action, target=str(target)[:255], detail=str(detail)[:2000]))
            s.commit()
    except Exception:
        pass


def list_audit(limit: int = 200) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
        return [{
            "id": a.id, "admin_email": a.admin_email, "action": a.action,
            "target": a.target, "detail": a.detail,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in rows]


# ---------- 站內公告 ----------
def _ann_dict(a: "Announcement") -> dict:
    return {"id": a.id, "title": a.title, "body": a.body, "level": a.level, "active": a.active,
            "created_at": a.created_at.isoformat() if a.created_at else None}


def create_announcement(data: dict) -> dict:
    with SessionLocal() as s:
        a = Announcement(title=data.get("title", ""), body=data.get("body", ""),
                         level=data.get("level", "info"), active=data.get("active", True))
        s.add(a)
        s.commit()
        s.refresh(a)
        return _ann_dict(a)


def list_announcements(active_only: bool = False) -> list[dict]:
    with SessionLocal() as s:
        q = select(Announcement)
        if active_only:
            q = q.where(Announcement.active == True)  # noqa: E712
        rows = s.scalars(q.order_by(Announcement.created_at.desc())).all()
        return [_ann_dict(a) for a in rows]


def delete_announcement(ann_id: int) -> bool:
    with SessionLocal() as s:
        a = s.get(Announcement, ann_id)
        if not a:
            return False
        s.delete(a)
        s.commit()
        return True


# ---------- 檢舉 ----------
def create_report(reporter_id: int, target_type: str, target_id: int, reason: str) -> dict:
    with SessionLocal() as s:
        r = Report(reporter_id=reporter_id, target_type=target_type, target_id=target_id, reason=reason[:500])
        s.add(r)
        s.commit()
        s.refresh(r)
        return {"id": r.id, "status": r.status}


def list_reports(status: str | None = "open", limit: int = 200) -> list[dict]:
    with SessionLocal() as s:
        q = select(Report)
        if status:
            q = q.where(Report.status == status)
        rows = s.scalars(q.order_by(Report.created_at.desc()).limit(limit)).all()
        return [{
            "id": r.id, "target_type": r.target_type, "target_id": r.target_id,
            "reason": r.reason, "reporter_id": r.reporter_id, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]


def resolve_report(report_id: int) -> bool:
    with SessionLocal() as s:
        r = s.get(Report, report_id)
        if not r:
            return False
        r.status = "resolved"
        s.commit()
        return True


# ---------- App 設定(SEO 等)----------
def get_app_settings() -> dict:
    with SessionLocal() as s:
        return {k: v for (k, v) in s.execute(select(AppSetting.key, AppSetting.value)).all()}


def save_app_settings(data: dict) -> None:
    with SessionLocal() as s:
        for k, v in data.items():
            row = s.get(AppSetting, k)
            if row is None:
                s.add(AppSetting(key=k, value=str(v)))
            else:
                row.value = str(v)
        s.commit()


def save_page_seo(path: str, data: dict) -> None:
    import json as _json
    save_app_settings({f"page:{path}": _json.dumps({
        "title": data.get("title", ""), "description": data.get("description", ""),
        "keywords": data.get("keywords", ""),
    }, ensure_ascii=False)})


def get_page_seo(path: str) -> dict:
    import json as _json
    with SessionLocal() as s:
        row = s.get(AppSetting, f"page:{path}")
        if not row or not row.value:
            return {}
        try:
            return _json.loads(row.value)
        except Exception:
            return {}


def list_page_seo() -> list[dict]:
    import json as _json
    with SessionLocal() as s:
        rows = s.execute(select(AppSetting.key, AppSetting.value)).all()
    out = []
    for k, v in rows:
        if k.startswith("page:"):
            try:
                d = _json.loads(v)
            except Exception:
                d = {}
            out.append({"path": k[5:], **d})
    return out


def set_privilege(user_id: int, privileged: bool) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        u.privileged = bool(privileged)
        s.commit()
        return True


def set_username(user_id: int, username: str) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        u.username = (username or "")[:60]
        s.commit()
        return True


def quota_use(user_id: int, kind: str, limit: int) -> tuple[bool, int]:
    """嘗試用掉一次每日額度。回傳 (是否允許, 用後次數)。"""
    day = _now().strftime("%Y-%m-%d")
    with SessionLocal() as s:
        row = s.get(Usage, (user_id, day))
        if row is None:
            row = Usage(user_id=user_id, day=day, ai=0, search=0)
            s.add(row)
        cur = getattr(row, kind, 0) or 0
        if cur >= limit:
            return False, cur
        setattr(row, kind, cur + 1)
        s.commit()
        return True, cur + 1


def quota_today(user_id: int) -> dict:
    day = _now().strftime("%Y-%m-%d")
    with SessionLocal() as s:
        row = s.get(Usage, (user_id, day))
        return {"ai": (row.ai if row else 0), "search": (row.search if row else 0)}


def is_privileged(user_id: int) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        return bool(u and u.privileged)


def _fav_dict(f: "Favorite") -> dict:
    return {
        "id": f.id, "url": f.url, "title": f.title, "image_url": f.image_url,
        "domain": f.domain, "price": f.price, "target_twd": f.target_twd,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def list_favorites(user_id: int) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())).all()
        return [_fav_dict(f) for f in rows]


def favorite_urls(user_id: int) -> list[str]:
    with SessionLocal() as s:
        return [u for (u,) in s.execute(select(Favorite.url).where(Favorite.user_id == user_id)).all()]


def add_favorite(user_id: int, data: dict) -> dict:
    with SessionLocal() as s:
        f = s.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.url == data.get("url", "")))
        if f is None:
            f = Favorite(user_id=user_id, url=data.get("url", ""))
            s.add(f)
        f.title = data.get("title", "")[:300]
        f.image_url = data.get("image_url", "")
        f.domain = data.get("domain", "")
        f.price = data.get("price", "")
        s.commit()
        s.refresh(f)
        return _fav_dict(f)


def set_favorite_target(fav_id: int, user_id: int, target_twd: int | None) -> dict | None:
    with SessionLocal() as s:
        f = s.get(Favorite, fav_id)
        if f is None or f.user_id != user_id:
            return None
        f.target_twd = target_twd
        s.commit()
        s.refresh(f)
        return _fav_dict(f)


def remove_favorite(fav_id: int, user_id: int) -> bool:
    with SessionLocal() as s:
        f = s.get(Favorite, fav_id)
        if f is None or f.user_id != user_id:
            return False
        s.delete(f)
        s.commit()
        return True


def price_history(user_id: int, url: str) -> list[dict]:
    """掃使用者所有歷史搜尋,回傳某網址的價格(台幣)隨時間變化。"""
    out: list[dict] = []
    with SessionLocal() as s:
        runs = s.scalars(select(Run).where(Run.user_id == user_id).order_by(Run.finished_at.asc())).all()
        for r in runs:
            for rec in (r.records or []):
                if rec.get("url") == url and rec.get("price"):
                    twd = money.to_twd(rec.get("price", ""))
                    if twd:
                        out.append({
                            "date": r.finished_at.isoformat() if r.finished_at else None,
                            "price_twd": twd, "price": rec.get("price", ""),
                        })
                    break
    return out


def list_favorites_with_target(user_id: int) -> list[dict]:
    """給通知檢查用:有設目標價的收藏。"""
    with SessionLocal() as s:
        rows = s.scalars(select(Favorite).where(Favorite.user_id == user_id, Favorite.target_twd.isnot(None))).all()
        return [_fav_dict(f) for f in rows]


def set_user_note(user_id: int, note: str, tags: list) -> bool:
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            return False
        u.admin_note = note
        u.tags = tags
        s.commit()
        return True


# ---------- 部落格 ----------

def _post_dict(p: "Post", full: bool = False, author_name: str = "") -> dict:
    d = {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "excerpt": p.excerpt or "",
        "cover_image": p.cover_image or "",
        "category": p.category or "",
        "tags": p.tags or [],
        "published": p.published,
        "author_id": p.author_id,
        "author": author_name,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if full:
        d["content"] = p.content or ""
    return d


def _author_map(s, posts: list) -> dict[int, str]:
    ids = {p.author_id for p in posts}
    if not ids:
        return {}
    rows = s.execute(select(User.id, User.username, User.email).where(User.id.in_(ids))).all()
    return {uid: (uname or (email.split("@")[0] if email else "")) for uid, uname, email in rows}


def _unique_slug(s, base: str) -> str:
    base = base or "post"
    slug = base
    i = 2
    while s.scalar(select(Post).where(Post.slug == slug)):
        slug = f"{base}-{i}"
        i += 1
    return slug


def list_published_posts(category: str | None = None) -> list[dict]:
    with SessionLocal() as s:
        q = select(Post).where(Post.published == True)  # noqa: E712
        if category:
            q = q.where(Post.category == category)
        rows = s.scalars(q.order_by(Post.created_at.desc())).all()
        names = _author_map(s, rows)
        return [_post_dict(p, author_name=names.get(p.author_id, "")) for p in rows]


def list_all_posts() -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Post).order_by(Post.created_at.desc())).all()
        names = _author_map(s, rows)
        return [_post_dict(p, author_name=names.get(p.author_id, "")) for p in rows]


def list_user_posts(author_id: int) -> list[dict]:
    with SessionLocal() as s:
        rows = s.scalars(select(Post).where(Post.author_id == author_id).order_by(Post.created_at.desc())).all()
        names = _author_map(s, rows)
        return [_post_dict(p, author_name=names.get(p.author_id, "")) for p in rows]


def get_post_by_slug(slug: str, only_published: bool = True) -> dict | None:
    with SessionLocal() as s:
        p = s.scalar(select(Post).where(Post.slug == slug))
        if p is None or (only_published and not p.published):
            return None
        names = _author_map(s, [p])
        return _post_dict(p, full=True, author_name=names.get(p.author_id, ""))


def get_post(post_id: int) -> dict | None:
    with SessionLocal() as s:
        p = s.get(Post, post_id)
        if not p:
            return None
        names = _author_map(s, [p])
        return _post_dict(p, full=True, author_name=names.get(p.author_id, ""))


def post_owner(post_id: int) -> int | None:
    with SessionLocal() as s:
        p = s.get(Post, post_id)
        return p.author_id if p else None


def create_post(author_id: int, data: dict) -> dict:
    with SessionLocal() as s:
        slug = _unique_slug(s, (data.get("slug") or "").strip() or f"post")
        p = Post(
            slug=slug,
            title=data.get("title", "未命名"),
            excerpt=data.get("excerpt", ""),
            content=data.get("content", ""),
            cover_image=data.get("cover_image", ""),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            published=data.get("published", False),
            author_id=author_id,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return _post_dict(p, full=True)


def update_post(post_id: int, data: dict) -> dict | None:
    with SessionLocal() as s:
        p = s.get(Post, post_id)
        if p is None:
            return None
        for key in ("title", "excerpt", "content", "cover_image", "category", "tags", "published"):
            if key in data and data[key] is not None:
                setattr(p, key, data[key])
        if data.get("slug") and data["slug"].strip() != p.slug:
            p.slug = _unique_slug(s, data["slug"].strip())
        p.updated_at = _now()
        s.commit()
        s.refresh(p)
        return _post_dict(p, full=True)


def delete_post(post_id: int) -> bool:
    with SessionLocal() as s:
        p = s.get(Post, post_id)
        if p is None:
            return False
        s.delete(p)
        s.commit()
        return True


# ---------- 討論區 ----------

def _display_name(email: str) -> str:
    return (email or "匿名").split("@")[0]


def _thread_dict(t: "Thread", full: bool = False) -> dict:
    d = {
        "id": t.id,
        "category": t.category,
        "title": t.title,
        "author": _display_name(t.author_email),
        "author_id": t.author_id,
        "reply_count": t.reply_count,
        "likes": t.likes or 0,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "last_reply_at": t.last_reply_at.isoformat() if t.last_reply_at else None,
    }
    if full:
        d["content"] = t.content or ""
    return d


def _reply_dict(r: "Reply") -> dict:
    return {
        "id": r.id,
        "content": r.content or "",
        "author": _display_name(r.author_email),
        "author_id": r.author_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def like_thread(thread_id: int) -> int:
    with SessionLocal() as s:
        t = s.get(Thread, thread_id)
        if not t:
            return 0
        t.likes = (t.likes or 0) + 1
        s.commit()
        return t.likes


def list_threads(category: str | None = None, limit: int = 100) -> list[dict]:
    with SessionLocal() as s:
        q = select(Thread)
        if category:
            q = q.where(Thread.category == category)
        rows = s.scalars(q.order_by(Thread.last_reply_at.desc()).limit(limit)).all()
        return [_thread_dict(t) for t in rows]


def get_thread(thread_id: int) -> dict | None:
    with SessionLocal() as s:
        t = s.get(Thread, thread_id)
        if t is None:
            return None
        d = _thread_dict(t, full=True)
        replies = s.scalars(select(Reply).where(Reply.thread_id == thread_id).order_by(Reply.created_at.asc())).all()
        d["replies"] = [_reply_dict(r) for r in replies]
        return d


def create_thread(author_id: int, author_email: str, category: str, title: str, content: str) -> dict:
    with SessionLocal() as s:
        t = Thread(category=category, title=title[:300], content=content,
                   author_id=author_id, author_email=author_email)
        s.add(t)
        s.commit()
        s.refresh(t)
        return _thread_dict(t, full=True)


def create_reply(thread_id: int, author_id: int, author_email: str, content: str) -> dict | None:
    with SessionLocal() as s:
        t = s.get(Thread, thread_id)
        if t is None:
            return None
        r = Reply(thread_id=thread_id, content=content, author_id=author_id, author_email=author_email)
        s.add(r)
        t.reply_count = (t.reply_count or 0) + 1
        t.last_reply_at = _now()
        s.commit()
        s.refresh(r)
        return _reply_dict(r)


def delete_thread(thread_id: int, user_id: int, is_admin: bool = False) -> bool:
    with SessionLocal() as s:
        t = s.get(Thread, thread_id)
        if t is None or (t.author_id != user_id and not is_admin):
            return False
        for r in s.scalars(select(Reply).where(Reply.thread_id == thread_id)).all():
            s.delete(r)
        s.delete(t)
        s.commit()
        return True


def delete_reply(reply_id: int, user_id: int, is_admin: bool = False) -> bool:
    with SessionLocal() as s:
        r = s.get(Reply, reply_id)
        if r is None or (r.author_id != user_id and not is_admin):
            return False
        t = s.get(Thread, r.thread_id)
        if t and t.reply_count:
            t.reply_count -= 1
        s.delete(r)
        s.commit()
        return True
