"""把舊結構的 Postgres 資料複製到已跑過 migrate.py 的新資料庫(冪等,可重跑)。

用法(cd backend):
  python scripts/load_old_db.py --source <舊庫網址> --target <新庫網址>
  或設環境變數 SOURCE_DATABASE_URL、TARGET_DATABASE_URL。

- 來源連線設為唯讀;只讀舊表,絕不寫入。
- 目標用 ON CONFLICT (主鍵) DO UPDATE:重跑只會更新,不會重複。
- 依外鍵順序複製,結束時校正序號,並逐表比對筆數(有差異時以非零狀態結束)。
- 網址只從參數或環境變數讀取,程式不寫死、不印出。
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Json, Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BATCH = 500

# 依外鍵順序:先父表後子表(只列舊結構存在的表;新表不用複製)
TABLES = [
    "tr_users", "tr_runs", "tr_user_settings", "tr_schedules", "tr_watches", "tr_posts", "tr_post_comments",
    "tr_post_likes", "tr_post_comment_likes", "tr_post_reactions", "tr_threads", "tr_replies", "tr_favorites",
    "tr_audit", "tr_announcements", "tr_reports", "tr_crawl_items", "tr_scheduled_broadcasts", "tr_app_settings",
    "tr_subscriptions", "tr_ai_chat_log", "tr_bind_codes", "tr_bot_chat_log", "tr_push_subs", "tr_notifications",
    "tr_ai_cost", "tr_usage",
]


def _columns(conn, table: str) -> dict[str, str]:
    rows = conn.execute(
        """SELECT column_name, data_type FROM information_schema.columns
           WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position""",
        (table,),
    ).fetchall()
    return {name: dtype for name, dtype in rows}


def _primary_key(conn, table: str) -> list[str]:
    rows = conn.execute(
        """SELECT a.attname FROM pg_index i
           JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
           WHERE i.indrelid = (quote_ident(current_schema()) || '.' || quote_ident(%s))::regclass AND i.indisprimary
           ORDER BY array_position(i.indkey, a.attnum)""",
        (table,),
    ).fetchall()
    return [r[0] for r in rows]


def _adapt(value, target_type: str):
    if value is None:
        return None
    if target_type == "json":
        return Json(value)
    if target_type == "jsonb":
        return Jsonb(value)
    return value


def _copy_table(src, dst, table: str) -> int:
    src_cols = _columns(src, table)
    if not src_cols:
        print(f"  {table}: 來源沒有這張表,略過")
        return 0
    dst_cols = _columns(dst, table)
    cols = [c for c in src_cols if c in dst_cols]
    pk = _primary_key(dst, table)
    id_list = sql.SQL(", ").join(map(sql.Identifier, cols))
    updates = [c for c in cols if c not in pk]
    conflict = (
        sql.SQL("DO UPDATE SET {}").format(sql.SQL(", ").join(
            sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in updates))
        if updates else sql.SQL("DO NOTHING")
    )
    insert = sql.SQL("INSERT INTO {t} ({cols}) VALUES ({vals}) ON CONFLICT ({pk}) ").format(
        t=sql.Identifier(table), cols=id_list,
        vals=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
        pk=sql.SQL(", ").join(map(sql.Identifier, pk)),
    ) + conflict
    order = sql.SQL(", ").join(map(sql.Identifier, pk))
    copied = 0
    last = None
    while True:
        where = sql.SQL("")
        params: list = []
        if last is not None:
            where = sql.SQL("WHERE ({k}) > ({v})").format(
                k=order, v=sql.SQL(", ").join(sql.Placeholder() * len(pk)))
            params = list(last)
        query = sql.SQL("SELECT {cols} FROM {t} {where} ORDER BY {order} LIMIT {n}").format(
            cols=id_list, t=sql.Identifier(table), where=where, order=order, n=sql.Literal(BATCH))
        rows = src.execute(query, params).fetchall()
        if not rows:
            break
        adapted = [[_adapt(v, dst_cols[c]) for v, c in zip(row, cols)] for row in rows]
        with dst.transaction():
            with dst.cursor() as cur:
                cur.executemany(insert, adapted)
        copied += len(rows)
        pk_idx = [cols.index(k) for k in pk]
        last = [rows[-1][i] for i in pk_idx]
    return copied


def _fix_sequence(dst, table: str) -> None:
    seq = dst.execute("SELECT pg_get_serial_sequence(quote_ident(current_schema()) || '.' || quote_ident(%s), 'id')", (table,)).fetchone()
    if seq and seq[0]:
        dst.execute(sql.SQL("SELECT setval({s}::regclass, COALESCE((SELECT MAX(id) FROM {t}), 1), (SELECT MAX(id) FROM {t}) IS NOT NULL)")
                    .format(s=sql.Literal(seq[0]), t=sql.Identifier(table)))


def _count(conn, table: str) -> int:
    return conn.execute(sql.SQL("SELECT count(*) FROM {t}").format(t=sql.Identifier(table))).fetchone()[0]


def load(source: str, target: str) -> int:
    mismatches = 0
    with psycopg.connect(source, autocommit=True, prepare_threshold=None) as src, \
            psycopg.connect(target, autocommit=True, prepare_threshold=None) as dst:
        src.execute("SET default_transaction_read_only = on")
        if not _columns(dst, "tr_jobs"):
            sys.exit("目標資料庫還沒有 tr_jobs:請先在目標跑 python migrate.py")
        print(f"{'資料表':<28}{'來源':>10}{'目標':>10}")
        for table in TABLES:
            _copy_table(src, dst, table)
            if _columns(dst, table) and "id" in _columns(dst, table):
                _fix_sequence(dst, table)
            if not _columns(src, table):
                continue
            a, b = _count(src, table), _count(dst, table)
            mark = "" if a == b else "  <-- 不一致"
            print(f"{table:<28}{a:>10}{b:>10}{mark}")
            mismatches += 0 if a == b else 1
    if mismatches:
        print(f"[失敗] {mismatches} 張表筆數不一致")
    else:
        print("[完成] 所有資料表筆數一致")
    return 1 if mismatches else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.environ.get("SOURCE_DATABASE_URL", ""))
    ap.add_argument("--target", default=os.environ.get("TARGET_DATABASE_URL", ""))
    args = ap.parse_args()
    if not args.source or not args.target:
        sys.exit("請提供 --source / --target 或 SOURCE_DATABASE_URL / TARGET_DATABASE_URL")
    if args.source == args.target:
        sys.exit("來源與目標不可相同")
    sys.exit(load(args.source, args.target))


if __name__ == "__main__":
    main()
