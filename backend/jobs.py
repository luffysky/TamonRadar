"""爬蟲任務管理:背景執行緒跑爬蟲,事件存緩衝區供 SSE 即時讀取。

- 每個 job 綁定發起的使用者(user_id),完成後存進資料庫。
- 用 Semaphore 限制同時執行的爬蟲數量,避免多人同時用把記憶體/瀏覽器爆掉。
"""
import os
import threading
import uuid
from datetime import datetime, timezone

from crawler.config import CrawlConfig
from crawler.runner import run_crawl
import db
import quota

# 同時最多幾個爬蟲在跑;其餘排隊等待
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_CRAWLS", "2"))
_slots = threading.Semaphore(MAX_CONCURRENT)


class TooManyJobs(quota.QuotaExceeded):
    """這個使用者同時進行中的爬蟲任務已達上限。"""


class Job:
    def __init__(self, config: CrawlConfig, user_id: int):
        self.id = uuid.uuid4().hex[:12]
        self.config = config
        self.user_id = user_id
        self.status = "pending"          # pending | queued | running | done | error | stopped
        self.events: list[dict] = []
        self.result: dict | None = None
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def add_event(self, event: dict) -> None:
        with self._lock:
            event = {**event, "seq": len(self.events)}
            self.events.append(event)

    def events_since(self, index: int) -> list[dict]:
        with self._lock:
            return self.events[index:]

    def request_stop(self) -> None:
        self._stop.set()

    def should_stop(self) -> bool:
        return self._stop.is_set()

    @property
    def finished(self) -> bool:
        return self.status in ("done", "error", "stopped")


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def active_count(self, user_id: int) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.user_id == user_id and not j.finished)

    def create(self, config: CrawlConfig, user_id: int, max_active: int | None = None) -> Job:
        job = Job(config, user_id)
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j.user_id == user_id and not j.finished)
            if max_active is not None and active >= max_active:
                raise TooManyJobs(f"你已有 {active} 個爬蟲進行中(上限 {max_active} 個),請等它跑完或先停止。")
            self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _run(self, job: Job) -> None:
        # 併發控制:槽位滿了就排隊
        if not _slots.acquire(blocking=False):
            job.status = "queued"
            job.add_event({"type": "queued", "message": "前面還有爬蟲在跑,排隊中…"})
            _slots.acquire()
        try:
            job.status = "running"
            try:
                if job.config.site_url:
                    from crawler.site_crawler import run_site_crawl
                    try:
                        db.clear_crawl_items(job.id)   # 重跑時清掉舊的串流項目
                    except Exception:
                        pass
                    result = run_site_crawl(
                        job.config, on_event=job.add_event, should_stop=job.should_stop,
                        on_batch=lambda batch: db.append_crawl_items(job.id, batch),
                    )
                else:
                    result = run_crawl(
                        job.config,
                        on_event=job.add_event,
                        should_stop=job.should_stop,
                    )
                job.result = result
                job.status = "stopped" if job.should_stop() else "done"
                try:
                    db.save_run(job, job.user_id)
                except Exception as e:
                    job.add_event({"type": "warning", "message": f"歷史存檔失敗:{e}"})
            except Exception as e:
                job.status = "error"
                job.error = str(e)
                job.add_event({"type": "error", "message": f"爬蟲發生錯誤:{e}"})
                try:
                    db.save_run(job, job.user_id)  # 失敗的任務也要留紀錄,歷史才看得到
                except Exception as save_err:
                    job.add_event({"type": "warning", "message": f"歷史存檔失敗:{save_err}"})
        finally:
            _slots.release()


manager = JobManager()
