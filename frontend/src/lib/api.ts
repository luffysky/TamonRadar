import type { CrawlResult, HistoryRun, ProgressEvent } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export interface CrawlParams {
  keywords: string[];
  google_pages_per_keyword: number;
  max_detail_pages: number;
  headless: boolean;
  scrape_details: boolean;
  search_provider?: string;
}

export interface HealthInfo {
  ok: boolean;
  default_keywords: string[];
  search_providers: Record<string, boolean>;
  default_provider: string;
}

export async function getHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("無法連線後端");
  return res.json();
}

export async function startCrawl(params: CrawlParams): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/crawl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("啟動爬蟲失敗");
  return res.json();
}

export async function stopCrawl(jobId: string): Promise<void> {
  await fetch(`${API_BASE}/api/crawl/${jobId}/stop`, { method: "POST" });
}

export async function getCrawl(jobId: string) {
  const res = await fetch(`${API_BASE}/api/crawl/${jobId}`);
  if (!res.ok) throw new Error("讀取任務失敗");
  return res.json();
}

/** 用 SSE 訂閱進度。回傳一個關閉函式。 */
export function streamCrawl(
  jobId: string,
  onProgress: (e: ProgressEvent) => void,
  onEnd: (payload: { status: string; result: CrawlResult | null; error: string | null }) => void,
  onError: () => void
): () => void {
  const es = new EventSource(`${API_BASE}/api/crawl/${jobId}/stream`);

  es.addEventListener("progress", (ev) => {
    try {
      onProgress(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore */
    }
  });

  es.addEventListener("end", (ev) => {
    try {
      onEnd(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore */
    }
    es.close();
  });

  es.onerror = () => {
    onError();
    es.close();
  };

  return () => es.close();
}

export async function getHistory(): Promise<{ runs: HistoryRun[] }> {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) throw new Error("讀取歷史失敗");
  return res.json();
}

export async function getHistoryRun(id: string): Promise<CrawlResult & { keywords: string[] }> {
  const res = await fetch(`${API_BASE}/api/history/${id}`);
  if (!res.ok) throw new Error("讀取歷史紀錄失敗");
  return res.json();
}

export async function summarize(runId: string): Promise<{ available: boolean; summary: string }> {
  const res = await fetch(`${API_BASE}/api/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
  if (!res.ok) throw new Error("AI 摘要失敗");
  return res.json();
}

export function exportUrl(runId: string, fmt: "csv" | "xlsx" | "md"): string {
  return `${API_BASE}/api/export/${runId}.${fmt}`;
}
