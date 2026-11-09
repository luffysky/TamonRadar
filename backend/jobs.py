"""持久化工作佇列:所有狀態都在資料庫(tr_jobs / tr_job_events / tr_crawl_frontier)。

Vercel Function 回應後會被凍結,任何行程內狀態都不可靠,所以:
- 建立工作只寫一筆 queued,立即回應;由 worker 認領執行(FOR UPDATE SKIP LOCKED + 認領鎖)。
- 工作者在時間預算內執行,進度/斷點寫回 DB,預算用完就放回佇列,下一輪從斷點接著跑。
- 工作者崩潰時靠心跳逾時回收;圍欄 token 確保舊工作者不能再寫入。
"""
import hashlib
import os
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, fields
from datetime import timedelta

from sqlalchemy import delete, func, select, text, update

from crawler.config import BudgetExhausted, CrawlConfig
import db
import quota

__all__ = ["BudgetExhausted", "LostClaim", "TooManyJobs", "JobHandle", "manager"]

TERMINAL = ("done", "error", "stopped")
ACTIVE = ("queued", "running")
# 會耗用外部搜尋額度/佔用爬取量的工作,受全站併發與每人併發限制
CRAWL_KINDS = ("crawl", "site_crawl", "schedule")

MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_CRAWLS", "5"))
STALE_AFTER = int(os.environ.get("JOB_STALE_SECONDS", "180"))   # 心跳多久沒更新視為工作者已死
HEARTBEAT_EVERY = 3.0   # 心跳/讀取停止旗標的最小間隔(秒)
EVENT_FLUSH_EVERY = 1.0
EVENT_FLUSH_SIZE = 25
FRONTIER_FETCH = 50
PREVIEW_CAP = 1000

_CLAIM_LOCK = (727100, 0)
_USER_LOCK_CLASS = 727101


class TooManyJobs(quota.QuotaExceeded):
    """這個使用者同時進行中的爬蟲任務已達上限。"""


class LostClaim(Exception):
    """這個工作已被別的工作者接手(圍欄失效),目前的工作者必須立刻停手。"""


def _xact_lock(s, classid: int, objid: int) -> None:
    """交易層級的 advisory lock(PgBouncer transaction 模式下安全);SQLite 本身就只有一個寫入者。"""
    if not db.IS_SQLITE:
        s.execute(text("SELECT pg_advisory_xact_lock(:a, :b)"), {"a": classid, "b": objid})


def config_to_dict(config: CrawlConfig) -> dict:
    return asdict(config)


def config_from_dict(data: dict) -> CrawlConfig:
    known = {f.name for f in fields(CrawlConfig)}
    return CrawlConfig(**{k: v for k, v in (data or {}).items() if k in known})


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def _add_job(s, kind: str, *, user_id: int | None = None, config: dict | None = None, job_id: str | None = None,
             dedupe_key: str | None = None, priority: int = 0, max_attempts: int = 3) -> str | None:
    """在呼叫端的交易內新增工作;dedupe_key 已存在時回 None(同一件事只排一次)。"""
    jid = job_id or new_job_id()
    now = db._now()
    values = dict(id=jid, user_id=user_id, kind=kind, status="queued", priority=priority, config=config or {},
                  cursor={}, error="", stop_requested=False, attempts=0, max_attempts=max_attempts, claimed_by="",
                  available_at=now, dedupe_key=dedupe_key, created_at=now)
    stmt = db.dialect_insert(db.Job).values(**values)
    stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_key"]) if dedupe_key else stmt
    return s.execute(stmt.returning(db.Job.id)).scalar()   # rowcount 在 Postgres 的 RETURNING 下不可靠


def enqueue(kind: str, **kw) -> str | None:
    with db.SessionLocal() as s:
        jid = _add_job(s, kind, **kw)
        s.commit()
        return jid


def _max_seq(s, job_id: str) -> int:
    return int(s.scalar(select(func.coalesce(func.max(db.JobEvent.seq), -1)).where(db.JobEvent.job_id == job_id)))


def _add_event(s, job_id: str, event: dict) -> None:
    seq = _max_seq(s, job_id) + 1
    s.add(db.JobEvent(job_id=job_id, seq=seq, event={**event, "seq": seq}))


def _release_claim(s, job) -> None:
    """工作結束後釋放排程/監看的認領欄位,下一次到期才能再派工。"""
    model = {"schedule": db.Schedule, "watch": db.Watch}.get(job.kind)
    if model is not None:
        s.execute(update(model).where(model.claim_job_id == job.id).values(claimed_at=None, claim_job_id=None))


def _save_failed_run(s, job, status: str, message: str = "") -> None:
    if job.kind in CRAWL_KINDS and job.user_id is not None:
        keywords = (job.config or {}).get("keywords") or []
        db.store_run(s, job.id, job.user_id, status, keywords, {"records": [], "summary": {}, "error": message})


# ---------- 查詢(給 API 用)----------

@dataclass
class JobView:
    id: str
    user_id: int | None
    kind: str
    status: str
    error: str | None
    config: dict
    stop_requested: bool

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL


def _view(job) -> JobView:
    return JobView(id=job.id, user_id=job.user_id, kind=job.kind, status=job.status, error=job.error or None,
                   config=job.config or {}, stop_requested=bool(job.stop_requested))


class JobManager:
    def active_count(self, user_id: int) -> int:
        with db.SessionLocal() as s:
            return self._active(s, user_id)

    @staticmethod
    def _active(s, user_id: int) -> int:
        return int(s.scalar(select(func.count()).select_from(db.Job).where(
            db.Job.user_id == user_id, db.Job.status.in_(ACTIVE), db.Job.kind.in_(("crawl", "site_crawl")))) or 0)

    def create(self, config: CrawlConfig, user_id: int, max_active: int | None = None) -> JobView:
        kind = "site_crawl" if config.site_url else "crawl"
        with db.SessionLocal() as s:
            _xact_lock(s, _USER_LOCK_CLASS, user_id)  # 同一使用者的「檢查數量 + 建立」不可交錯
            active = self._active(s, user_id)
            if max_active is not None and active >= max_active:
                s.rollback()
                raise TooManyJobs(f"你已有 {active} 個爬蟲進行中(上限 {max_active} 個),請等它跑完或先停止。")
            jid = _add_job(s, kind, user_id=user_id, config=config_to_dict(config), priority=5)
            _add_event(s, jid, {"type": "queued", "message": "排隊中,馬上開始…"})
            s.commit()
            return _view(s.get(db.Job, jid))

    def get(self, job_id: str) -> JobView | None:
        with db.SessionLocal() as s:
            job = s.get(db.Job, job_id)
            return _view(job) if job is not None else None

    def stop(self, job_id: str) -> str | None:
        """要求停止:還沒開始的直接結束,執行中的由工作者讀到旗標後收尾。回傳新狀態。"""
        with db.SessionLocal() as s:
            job = s.get(db.Job, job_id, with_for_update=True)
            if job is None:
                return None
            if job.status in TERMINAL:
                return job.status
            if job.status == "queued" and not job.cursor:
                job.status = "stopped"
                job.finished_at = db._now()
                job.stop_requested = True
                _add_event(s, job.id, {"type": "stopped", "message": "已被使用者停止"})
                _release_claim(s, job)
                _save_failed_run(s, job, "stopped")
                s.commit()
                return "stopped"
            job.stop_requested = True
            s.commit()
            return "stopping"


manager = JobManager()


def events_since(job_id: str, after: int = -1, limit: int = 200) -> list[dict]:
    with db.SessionLocal() as s:
        rows = s.scalars(select(db.JobEvent.event).where(db.JobEvent.job_id == job_id, db.JobEvent.seq > after)
                         .order_by(db.JobEvent.seq).limit(limit)).all()
    return list(rows)


def result_of(job: JobView) -> dict | None:
    """已完成任務的結果(來自 tr_runs;整站爬多於預覽的部分走 /api/run/{id}/items)。"""
    run = db.get_run(job.id)
    if run is None:
        return None
    records = run.get("records", [])
    total = max(len(records), db.count_crawl_items(job.id))
    return {"records": records, "summary": run.get("summary", {}), "total": total, "streamed": total > len(records)}


# ---------- 認領 ----------

def _reap_stale(s, now) -> None:
    cutoff = now - timedelta(seconds=STALE_AFTER)
    stale = s.scalars(select(db.Job).where(db.Job.status == "running", db.Job.heartbeat_at < cutoff)
                      .with_for_update(skip_locked=True).limit(50)).all()
    for job in stale:
        job.attempts = (job.attempts or 0) + 1
        job.claim_token = None
        job.claimed_by = ""
        job.heartbeat_at = None
        if job.attempts >= job.max_attempts:
            job.status = "error"
            job.error = "工作者多次中斷,已放棄此任務。"
            job.finished_at = now
            _add_event(s, job.id, {"type": "error", "message": job.error})
            _release_claim(s, job)
            _save_failed_run(s, job, "error", job.error)
        else:
            job.status = "queued"
            job.available_at = now
            _add_event(s, job.id, {"type": "info", "message": "處理程序中斷,稍後自動重試…"})


def claim_next(worker_id: str, deadline: float, job_id: str | None = None) -> "JobHandle | None":
    """認領下一個可執行的工作;job_id 指定時只認領該工作(同步執行/測試用)。"""
    now = db._now()
    with db.SessionLocal() as s:
        _xact_lock(s, *_CLAIM_LOCK)   # 併發計數必須與認領同一個臨界區,否則兩個工作者會同時超額
        _reap_stale(s, now)
        s.flush()
        running: Counter = Counter(uid for (uid,) in s.execute(
            select(db.Job.user_id).where(db.Job.status == "running", db.Job.kind.in_(CRAWL_KINDS))).all())
        total_running = sum(running.values())

        q = select(db.Job).where(db.Job.status == "queued", db.Job.available_at <= now)
        if job_id:
            q = q.where(db.Job.id == job_id)
        q = q.order_by(db.Job.priority.desc(), db.Job.available_at, db.Job.created_at).limit(100)
        q = q.with_for_update(skip_locked=True)

        user_caps: dict[int, int] = {}
        chosen = None
        for job in s.scalars(q).all():
            if job.kind in CRAWL_KINDS:
                if total_running >= MAX_CONCURRENT:
                    continue
                uid = job.user_id
                if uid not in user_caps:
                    user_caps[uid] = quota.caps_for(s.get(db.User, uid)).concurrent_jobs if uid else 1
                if running[uid] >= user_caps[uid]:
                    continue
            chosen = job
            break
        if chosen is None:
            s.commit()
            return None

        chosen.status = "running"
        chosen.claimed_by = worker_id[:40]
        chosen.claim_token = uuid.uuid4().hex
        chosen.heartbeat_at = now
        if chosen.started_at is None:
            chosen.started_at = now
        s.commit()
        return JobHandle(chosen, deadline, _max_seq(s, chosen.id) + 1)


class JobHandle:
    """工作者手上的一個工作:事件寫入、心跳、斷點都透過這裡,且都受圍欄保護。"""

    def __init__(self, job, deadline: float, next_seq: int):
        self.id = job.id
        self.user_id = job.user_id
        self.kind = job.kind
        self.config = dict(job.config or {})
        self.cursor = dict(job.cursor or {})
        self.token = job.claim_token
        self.deadline = deadline
        self._seq = next_seq
        self._buf: list[dict] = []
        self._last_flush = 0.0
        self._last_beat = time.monotonic()
        self._stop = bool(job.stop_requested)
        self.finished = False

    # 事件 ----------
    def add_event(self, event: dict) -> None:
        self._buf.append({**event, "seq": self._seq})
        self._seq += 1
        if len(self._buf) >= EVENT_FLUSH_SIZE or time.monotonic() - self._last_flush >= EVENT_FLUSH_EVERY:
            self.flush_events()

    def flush_events(self) -> None:
        if not self._buf:
            return
        rows = [{"job_id": self.id, "seq": e["seq"], "event": e, "created_at": db._now()} for e in self._buf]
        try:
            with db.SessionLocal() as s:
                s.execute(db.dialect_insert(db.JobEvent).values(rows).on_conflict_do_nothing(index_elements=["job_id", "seq"]))
                s.commit()
        except Exception as e:
            print(f"[job {self.id}] 事件寫入失敗,稍後重試:{e}")   # 進度事件不該拖垮工作本身
            return
        self._buf = []
        self._last_flush = time.monotonic()

    # 心跳 / 停止 ----------
    def _fenced(self):
        return (db.Job.id == self.id, db.Job.claim_token == self.token, db.Job.status == "running")

    def _beat(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_beat < HEARTBEAT_EVERY:
            return
        with db.SessionLocal() as s:
            row = s.execute(update(db.Job).where(*self._fenced()).values(heartbeat_at=db._now())
                            .returning(db.Job.stop_requested)).first()
            s.commit()
        if row is None:
            raise LostClaim(self.id)
        self._stop = bool(row[0])
        self._last_beat = now

    def should_stop(self) -> bool:
        self._beat()
        return self._stop

    def budget_left(self) -> bool:
        return time.monotonic() < self.deadline

    def keepalive(self) -> bool:
        """維持心跳;回傳本輪預算是否還夠(長迴圈用)。"""
        self._beat()
        return self.budget_left()

    # 斷點 / 收尾 ----------
    def checkpoint(self, cursor: dict) -> None:
        with db.SessionLocal() as s:
            row = s.execute(update(db.Job).where(*self._fenced()).values(cursor=cursor, heartbeat_at=db._now())
                            .returning(db.Job.stop_requested)).first()
            s.commit()
        if row is None:
            raise LostClaim(self.id)
        self.cursor = dict(cursor)
        self._stop = bool(row[0])      # 斷點等同一次心跳:這裡不讀旗標的話,頻繁存檔時永遠看不到停止請求
        self._last_beat = time.monotonic()

    def requeue(self) -> None:
        """本輪時間到:放回佇列,下一輪從 cursor 接著跑(不算失敗,attempts 不增加)。"""
        self.add_event({"type": "info", "message": "本輪處理時間到,稍後自動接續…"})
        self.flush_events()
        with db.SessionLocal() as s:
            n = s.execute(update(db.Job).where(*self._fenced()).values(
                status="queued", claim_token=None, claimed_by="", heartbeat_at=None, available_at=db._now())).rowcount
            s.commit()
        if n != 1:
            raise LostClaim(self.id)
        self.finished = True

    def finish(self, status: str, error: str = "", result: dict | None = None, keywords: list | None = None,
               save_run: bool = True) -> None:
        self.flush_events()
        with db.SessionLocal() as s:
            job = s.scalars(select(db.Job).where(*self._fenced()).with_for_update()).first()
            if job is None:
                raise LostClaim(self.id)
            job.status = status
            job.error = (error or "")[:2000]
            job.finished_at = db._now()
            job.cursor = {}
            job.claim_token = None
            job.claimed_by = ""
            if job.kind.startswith("bot_"):
                job.config = {}   # 互動 token / 對話內容不留在佇列裡
            _release_claim(s, job)
            if save_run and self.kind in CRAWL_KINDS and self.user_id is not None:
                db.store_run(s, self.id, self.user_id, status, keywords if keywords is not None else self.config.get("keywords", []), result)
            s.execute(delete(db.CrawlFrontier).where(db.CrawlFrontier.job_id == self.id))
            s.commit()
        self.finished = True


# ---------- 整站爬的 DB frontier ----------

class DbSiteStore:
    """整站爬的持久化存放:待抓佇列、已見網址、項目去重全部在 DB,單頁寫入是一個交易(精確一次)。"""

    def __init__(self, handle: JobHandle):
        self.h = handle
        st = handle.cursor
        self.pages = int(st.get("pages", 0))
        self.total = int(st.get("total", 0))
        self.with_price = int(st.get("with_price", 0))
        self.cats: Counter = Counter(st.get("cats") or {})
        self.doms: Counter = Counter(st.get("doms") or {})
        self._seeded = bool(st.get("seeded"))
        self._queue: list[tuple[str, int]] = []

    def _state(self) -> dict:
        return {"seeded": True, "pages": self.pages, "total": self.total, "with_price": self.with_price,
                "cats": dict(self.cats), "doms": dict(self.doms)}

    @staticmethod
    def _frontier_rows(job_id: str, links: list[tuple[str, int]]) -> list[dict]:
        return [{"job_id": job_id, "url_hash": db.url_hash(u), "url": u, "depth": d, "status": "pending"} for u, d in links]

    def _insert_links(self, s, links: list[tuple[str, int]]) -> None:
        for i in range(0, len(links), 1000):
            s.execute(db.dialect_insert(db.CrawlFrontier).values(self._frontier_rows(self.h.id, links[i:i + 1000]))
                      .on_conflict_do_nothing(index_elements=["job_id", "url_hash"]))

    def seed(self, start: str) -> None:
        if self._seeded:
            return
        with db.SessionLocal() as s:
            self._insert_links(s, [(start, 0)])
            s.commit()
        self._seeded = True
        self.h.checkpoint(self._state())

    def next(self) -> tuple[str, int] | None:
        if not self._queue:
            with db.SessionLocal() as s:
                rows = s.execute(select(db.CrawlFrontier.url, db.CrawlFrontier.depth).where(
                    db.CrawlFrontier.job_id == self.h.id, db.CrawlFrontier.status == "pending")
                    .order_by(db.CrawlFrontier.id).limit(FRONTIER_FETCH)).all()
            self._queue = [(u, d) for u, d in rows]
        return self._queue.pop(0) if self._queue else None

    def skip(self, url: str) -> None:
        with db.SessionLocal() as s:
            s.execute(update(db.CrawlFrontier).where(db.CrawlFrontier.job_id == self.h.id,
                                                     db.CrawlFrontier.url_hash == db.url_hash(url)).values(status="skip"))
            s.commit()

    def commit_page(self, url: str, items: list[dict], links: list[tuple[str, int]]) -> int:
        """一頁的項目 + 新連結 + 計數在同一個交易寫入;回傳實際新增的項目數。"""
        keyed = {}
        for it in items:
            keyed[hashlib.sha256(f"{it.get('title', '')}|{it.get('url', '')}".encode("utf-8", "replace")).hexdigest()[:40]] = it
        with db.SessionLocal() as s:
            inserted: set[str] = set()
            if keyed:
                rows = [{"run_id": self.h.id, "payload": it, "dedupe_key": k} for k, it in keyed.items()]
                for i in range(0, len(rows), 1000):
                    inserted |= set(s.scalars(db.dialect_insert(db.CrawlItem).values(rows[i:i + 1000])
                                              .on_conflict_do_nothing(index_elements=["run_id", "dedupe_key"])
                                              .returning(db.CrawlItem.dedupe_key)).all())
            if links:
                self._insert_links(s, links)
            s.execute(update(db.CrawlFrontier).where(db.CrawlFrontier.job_id == self.h.id,
                                                     db.CrawlFrontier.url_hash == db.url_hash(url)).values(status="done"))
            self.pages += 1
            for k in inserted:
                it = keyed[k]
                self.total += 1
                self.cats[it.get("category") or "未分類"] += 1
                self.doms[it.get("domain") or "unknown"] += 1
                if (it.get("price") or "").strip():
                    self.with_price += 1
            state = self._state()
            n = s.execute(update(db.Job).where(*self.h._fenced()).values(cursor=state, heartbeat_at=db._now())).rowcount
            if n != 1:
                s.rollback()
                raise LostClaim(self.h.id)
            s.commit()
        self.h.cursor = state
        return len(inserted)

    def preview(self, cap: int) -> list[dict]:
        return db.list_crawl_items(self.h.id, 0, cap)
