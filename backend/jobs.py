"""爬蟲任務管理:把一次爬蟲跑在背景執行緒,事件存在緩衝區供 SSE 即時讀取。

設計選擇:事件用 list 緩衝(而非只用 queue),這樣 SSE 端點可以「補播」已發生的
事件,使用者中途連線也看得到完整進度,對教學除錯也友善。
"""
import threading
import uuid
from datetime import datetime, timezone

from crawler.config import CrawlConfig
from crawler.runner import run_crawl
import history


class Job:
    def __init__(self, config: CrawlConfig):
        self.id = uuid.uuid4().hex[:12]
        self.config = config
        self.status = "pending"          # pending | running | done | error | stopped
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

    def create(self, config: CrawlConfig) -> Job:
        job = Job(config)
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _run(self, job: Job) -> None:
        job.status = "running"
        try:
            result = run_crawl(
                job.config,
                on_event=job.add_event,
                should_stop=job.should_stop,
            )
            job.result = result
            job.status = "stopped" if job.should_stop() else "done"
            try:
                history.save_run(job)
            except Exception as e:  # 歷史存檔失敗不該讓整個任務算失敗
                job.add_event({"type": "warning", "message": f"歷史存檔失敗:{e}"})
        except Exception as e:
            job.status = "error"
            job.error = str(e)
            job.add_event({"type": "error", "message": f"爬蟲發生錯誤:{e}"})


manager = JobManager()
