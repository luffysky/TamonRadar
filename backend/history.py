"""歷史紀錄:每次完成的搜尋存成一個 JSON 檔,供前端回看與比較。"""
import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_DIR = Path(__file__).parent / "data" / "history"


def _ensure_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_run(job) -> Path:
    _ensure_dir()
    result = job.result or {"records": [], "summary": {}}
    payload = {
        "id": job.id,
        "created_at": job.created_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": job.status,
        "keywords": job.config.keywords,
        "summary": result.get("summary", {}),
        "records": result.get("records", []),
    }
    path = HISTORY_DIR / f"{job.id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_runs() -> list[dict]:
    """回傳歷史清單(不含完整 records,只有摘要),依時間新到舊。"""
    _ensure_dir()
    runs = []
    for path in HISTORY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        runs.append({
            "id": data.get("id"),
            "created_at": data.get("created_at"),
            "finished_at": data.get("finished_at"),
            "status": data.get("status"),
            "keywords": data.get("keywords", []),
            "summary": data.get("summary", {}),
        })
    runs.sort(key=lambda r: r.get("finished_at") or "", reverse=True)
    return runs


def get_run(run_id: str) -> dict | None:
    path = HISTORY_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
