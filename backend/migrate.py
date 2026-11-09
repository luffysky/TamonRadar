"""資料庫結構遷移:依檔名順序執行 migrations/*.sql,已套用的記在 schema_migrations。

用法(cd backend):
  python migrate.py            # 套用所有尚未執行的遷移
  python migrate.py --status   # 只列出狀態
  python migrate.py --verify   # 比對資料庫與 ORM 的表/欄位是否一致

連線來源:DATABASE_URL_UNPOOLED,沒有才用 DATABASE_URL(DDL 與 session 層級鎖都要直連)。
刻意不在應用程式啟動時跑,部署前手動或由 CI 執行一次。
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_LOCK_KEY = 7227100


def _conninfo() -> str:
    url = (os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("DATABASE_URL") or "").strip()
    if not url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        sys.exit("請設定 Postgres 的 DATABASE_URL_UNPOOLED 或 DATABASE_URL")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _ensure_table(conn: psycopg.Connection) -> dict[str, str]:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""")
    return dict(conn.execute("SELECT filename, checksum FROM schema_migrations").fetchall())


def migrate(conninfo: str, status_only: bool = False) -> int:
    pending = 0
    with psycopg.connect(conninfo, autocommit=True, prepare_threshold=None) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
        try:
            applied = _ensure_table(conn)
            for path in _files():
                sql = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                if path.name in applied:
                    if applied[path.name] != checksum:
                        sys.exit(f"[錯誤] {path.name} 已套用但內容被改過;遷移檔不可回頭修改,請新增下一號")
                    print(f"  已套用  {path.name}")
                    continue
                pending += 1
                if status_only:
                    print(f"  待套用  {path.name}")
                    continue
                print(f"  執行中  {path.name}")
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                                 (path.name, checksum))
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
    return pending


def verify(conninfo: str) -> int:
    """比對 ORM 與實際資料庫;舊資料放寬的 NULL 屬於預期差異,只比對表名與欄名。"""
    os.environ.setdefault("APP_ENV", "test")
    if not os.environ.get("DATABASE_URL", "").startswith("postgres"):
        os.environ["DATABASE_URL"] = "sqlite://"
    import db
    from sqlalchemy import create_engine, inspect
    url = conninfo.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)
    insp = inspect(create_engine(url, connect_args={"prepare_threshold": None}))
    existing = set(insp.get_table_names())
    problems = []
    for t in db.Base.metadata.sorted_tables:
        if t.name not in existing:
            problems.append(f"缺少資料表 {t.name}")
            continue
        columns = {c["name"] for c in insp.get_columns(t.name)}
        missing = [c.name for c in t.columns if c.name not in columns]
        if missing:
            problems.append(f"{t.name} 缺少欄位 {missing}")
        extra = columns - {c.name for c in t.columns}
        if extra:
            problems.append(f"{t.name} 多出未在 ORM 的欄位 {sorted(extra)}")
    for p in problems:
        print("[問題]", p)
    print("[OK] ORM 與資料庫一致" if not problems else f"發現 {len(problems)} 個問題")
    return 1 if problems else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    conninfo = _conninfo()
    if args.verify:
        sys.exit(verify(conninfo))
    n = migrate(conninfo, status_only=args.status)
    print(f"完成,{'待套用' if args.status else '本次套用'} {n} 個遷移")


if __name__ == "__main__":
    main()
