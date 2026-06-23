"""資料庫連線診斷:讀 backend/.env 的 DATABASE_URL,連線並列出資料表與筆數。

用法:cd backend && python db_check.py
不會印出密碼,只印主機與資料表狀態。
"""
import os
from pathlib import Path
from urllib.parse import urlparse


def _load_env() -> None:
    env = Path(__file__).parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main() -> None:
    _load_env()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("❌ 找不到 DATABASE_URL(請在 backend/.env 設定)")
        return

    host = urlparse(url.replace("postgresql+psycopg", "postgresql")).hostname or "?"
    print(f"🔗 連線目標:{host}")

    import db  # 會用 DATABASE_URL 建立 engine
    from sqlalchemy import inspect, text

    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ 連線成功")
    except Exception as e:
        print(f"❌ 連線失敗:{e}")
        return

    db.init_db()
    print("✅ 資料表已確保建立")

    insp = inspect(db.engine)
    for tbl in insp.get_table_names():
        with db.engine.connect() as conn:
            n = conn.execute(text(f'SELECT count(*) FROM "{tbl}"')).scalar()
        print(f"  - {tbl}: {n} 筆")


if __name__ == "__main__":
    main()
