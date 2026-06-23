import type { CrawlResult, HistoryRun, ProgressEvent } from "./types";
import { authHeaders, clearSession, type AuthUser } from "./auth";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/** 401 代表 token 失效:清掉登入狀態並丟出特定錯誤,讓畫面導回登入頁。 */
function check401(res: Response): void {
  if (res.status === 401) {
    clearSession();
    throw new Error("UNAUTHORIZED");
  }
}

function jsonAuthHeaders(): Record<string, string> {
  return { "Content-Type": "application/json", ...authHeaders() };
}

// ---------- auth ----------

export async function register(email: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "註冊失敗");
  return res.json();
}

export async function getMe(token?: string): Promise<{ user: AuthUser }> {
  const headers = token ? { Authorization: `Bearer ${token}` } : authHeaders();
  const res = await fetch(`${API_BASE}/api/auth/me`, { headers });
  if (!res.ok) throw new Error("讀取使用者失敗");
  return res.json();
}

export function googleLoginUrl(): string {
  return `${API_BASE}/api/auth/google/login`;
}

export async function login(email: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "登入失敗");
  return res.json();
}

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
    headers: jsonAuthHeaders(),
    body: JSON.stringify(params),
  });
  check401(res);
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
  const res = await fetch(`${API_BASE}/api/history`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取歷史失敗");
  return res.json();
}

export async function getHistoryRun(id: string): Promise<CrawlResult & { keywords: string[] }> {
  const res = await fetch(`${API_BASE}/api/history/${id}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取歷史紀錄失敗");
  return res.json();
}

export async function summarize(runId: string): Promise<{ available: boolean; summary: string }> {
  const res = await fetch(`${API_BASE}/api/summarize`, {
    method: "POST",
    headers: jsonAuthHeaders(),
    body: JSON.stringify({ run_id: runId }),
  });
  check401(res);
  if (!res.ok) throw new Error("AI 摘要失敗");
  return res.json();
}

export function exportUrl(runId: string, fmt: "csv" | "xlsx" | "md"): string {
  return `${API_BASE}/api/export/${runId}.${fmt}`;
}

// ---------- 價格雷達 ----------

export interface RadarItem {
  title: string;
  url: string;
  domain: string;
  category: string;
  price: string;
  price_twd: number | null;
  image_url: string;
  old_price?: string;
  old_twd?: number;
  drop_pct?: number;
}

export interface RadarDiff {
  has_previous: boolean;
  previous_id?: string;
  previous_at?: string;
  diff?: {
    counts: { new: number; price_drops: number; restock: number };
    new_items: RadarItem[];
    price_drops: RadarItem[];
    restock: RadarItem[];
  };
}

export async function getHistoryDiff(id: string): Promise<RadarDiff> {
  const res = await fetch(`${API_BASE}/api/history/${id}/diff`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取價格雷達失敗");
  return res.json();
}
