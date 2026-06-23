"""資料庫層(SQLAlchemy)。

- 設了 DATABASE_URL(Supabase / Postgres)就連雲端資料庫。
- 沒設就退回本機 SQLite 檔(方便本機開發,不用裝 Postgres)。
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON, DateTime, ForeignKey, String, Text, create_engine, select,
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
        return url, {}
    # 本機 fallback:SQLite
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
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    runs: Mapped[list["Run"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="done")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    records: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="runs")


def init_db() -> None:
    Base.metadata.create_all(engine)


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
