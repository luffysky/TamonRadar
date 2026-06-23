"""資料庫層(SQLAlchemy)。

- 設了 DATABASE_URL(Supabase / Postgres)就連雲端資料庫。
- 沒設就退回本機 SQLite 檔(方便本機開發,不用裝 Postgres)。
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON, DateTime, ForeignKey, String, create_engine, inspect, select, text,
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
    password_hash: Mapped[str] = mapped_column(String(255), default="")  # OAuth 使用者為空
    provider: Mapped[str] = mapped_column(String(32), default="local")   # local | google
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

    user: Mapped["User"] = relationship(back_populates="runs")


class Settings(Base):
    __tablename__ = "tr_user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("tr_users.id"), primary_key=True)
    discord_webhook: Mapped[str] = mapped_column(String(500), default="")
    telegram_token: Mapped[str] = mapped_column(String(200), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(100), default="")


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """相容既有資料庫:補上後來新增的欄位(create_all 不會改既有表)。"""
    insp = inspect(engine)
    if "tr_users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("tr_users")}
    if "provider" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tr_users ADD COLUMN provider VARCHAR(32) DEFAULT 'local'"))


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
    with SessionLocal() as s:
        st = s.get(Settings, user_id)
        if st is None:
            return {"discord_webhook": "", "telegram_token": "", "telegram_chat_id": ""}
        return {
            "discord_webhook": st.discord_webhook or "",
            "telegram_token": st.telegram_token or "",
            "telegram_chat_id": st.telegram_chat_id or "",
        }


def save_settings(user_id: int, discord_webhook: str, telegram_token: str, telegram_chat_id: str) -> None:
    with SessionLocal() as s:
        st = s.get(Settings, user_id)
        if st is None:
            st = Settings(user_id=user_id)
            s.add(st)
        st.discord_webhook = discord_webhook
        st.telegram_token = telegram_token
        st.telegram_chat_id = telegram_chat_id
        s.commit()


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
        for key in ("name", "url", "available_keywords", "unavailable_keywords", "interval_minutes", "enabled"):
            if key in data and data[key] is not None:
                setattr(w, key, data[key])
        s.commit()
        s.refresh(w)
        return _watch_dict(w)


def set_watch_status(watch_id: int, status: str) -> None:
    with SessionLocal() as s:
        w = s.get(Watch, watch_id)
        if w:
            w.last_status = status
            w.last_checked = _now()
            s.commit()


def delete_watch(watch_id: int, user_id: int) -> bool:
    with SessionLocal() as s:
        w = s.get(Watch, watch_id)
        if w is None or w.user_id != user_id:
            return False
        s.delete(w)
        s.commit()
        return True
