import type { CrawlResult, HistoryRun, ProgressEvent } from "./types";
import { authHeaders, clearSession, getStoredUser, setSession, type AuthUser } from "./auth";

export const API_BASE =
  (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

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

export async function changePassword(current_password: string, new_password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/change-password`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ current_password, new_password }),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "改密碼失敗");
  // 改密碼後舊 token 全部失效,換上後端發的新 token 維持登入
  const data = await res.json().catch(() => ({}));
  const user = getStoredUser();
  if (data.token && user) setSession(data.token, user);
}

export async function deleteAccount(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/me`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除帳號失敗");
}

export async function forgotPassword(email: string): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/auth/forgot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error("申請失敗");
  return res.json();
}

export async function resetPassword(token: string, password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "重設失敗");
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
  vertical?: string;
}

export async function scrapePage(url: string, keywords: string[] = []): Promise<{ run_id: string; records: CrawlResult["records"]; summary: CrawlResult["summary"] }> {
  const res = await fetch(`${API_BASE}/api/scrape-page`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ url, keywords }),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "整頁抓取失敗");
  return res.json();
}

export async function startSiteCrawl(url: string, max_pages = 40, max_depth = 2, keywords: string[] = [], path_includes: string[] = []): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/crawl-site`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ url, max_pages, max_depth, keywords, path_includes }),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "整站爬啟動失敗");
  return res.json();
}

export interface HealthInfo {
  ok: boolean;
  default_keywords: string[];
  search_providers: Record<string, boolean>;
  default_provider: string;
}

export async function uploadFile(file: File): Promise<{ url: string; name: string; type: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", headers: authHeaders(), body: fd });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "上傳失敗");
  return res.json();
}

export async function getHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("無法連線後端");
  return res.json();
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export async function askAssistant(question: string, history: ChatTurn[]): Promise<{ available: boolean; answer: string }> {
  const res = await fetch(`${API_BASE}/api/assistant`, {
    method: "POST",
    headers: jsonAuthHeaders(), // 帶上登入身分,讓小幫手能讀你的搜尋結果
    body: JSON.stringify({ question, history }),
  });
  if (!res.ok) throw new Error("助手回應失敗");
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

/** 用 SSE 訂閱進度,對斷線有韌性:短暫斷線自動重連、已完成則補抓結果、真的沒了才報錯。 */
export function streamCrawl(
  jobId: string,
  onProgress: (e: ProgressEvent) => void,
  onEnd: (payload: { status: string; result: CrawlResult | null; error: string | null }) => void,
  onError: () => void
): () => void {
  let closed = false;
  let retries = 0;
  let es: EventSource | null = null;

  const open = () => {
    es = new EventSource(`${API_BASE}/api/crawl/${jobId}/stream`);

    es.addEventListener("progress", (ev) => {
      try {
        onProgress(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("end", (ev) => {
      closed = true;
      try {
        onEnd(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* ignore */
      }
      es?.close();
    });

    es.onerror = async () => {
      es?.close();
      if (closed) return;
      // 嘗試從狀態端點補救:已完成就直接給結果,還在跑就重連
      try {
        const r = await fetch(`${API_BASE}/api/crawl/${jobId}`);
        if (r.ok) {
          const data = await r.json();
          if (["done", "error", "stopped"].includes(data.status)) {
            closed = true;
            onEnd({ status: data.status, result: data.result, error: data.error });
            return;
          }
          if (retries++ < 6) {
            setTimeout(open, 2000); // 還在跑 → 2 秒後重連
            return;
          }
        }
      } catch {
        /* ignore */
      }
      onError();
    };
  };

  open();
  return () => {
    closed = true;
    es?.close();
  };
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

// ---------- AI ----------

export async function aiChat(runId: string, question: string, history?: ChatTurn[]): Promise<{ available: boolean; answer: string }> {
  const res = await fetch(`${API_BASE}/api/ai/chat`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ run_id: runId, question, history }),
  });
  check401(res);
  if (!res.ok) throw new Error("AI 對話失敗");
  return res.json();
}

export async function aiCompare(runId: string, urls: string[]): Promise<{ available: boolean; answer: string }> {
  const res = await fetch(`${API_BASE}/api/ai/compare`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ run_id: runId, urls }),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "比較失敗");
  return res.json();
}

export async function aiKeywords(query: string): Promise<{ available: boolean; keywords: string[] }> {
  const res = await fetch(`${API_BASE}/api/ai/keywords`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ query }),
  });
  check401(res);
  if (!res.ok) throw new Error("產生關鍵字失敗");
  return res.json();
}

export async function aiClean(runId: string): Promise<{ available: boolean; noise_urls: string[]; noise_count?: number }> {
  const res = await fetch(`${API_BASE}/api/ai/clean`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ run_id: runId }),
  });
  check401(res);
  if (!res.ok) throw new Error("AI 整理失敗");
  return res.json();
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

// ---------- 通知設定 ----------

export interface NotifySettings {
  discord_webhook: string;
  discord_user_id: string;
  telegram_token: string;
  telegram_chat_id: string;
  openai_key: string;
  anthropic_key: string;
  gemini_key: string;
  groq_key: string;
  openrouter_key: string;
  ai_provider: string;
  daily_digest: boolean;
}

export async function getSettings(): Promise<NotifySettings> {
  const res = await fetch(`${API_BASE}/api/settings`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取設定失敗");
  return res.json();
}

export async function saveSettings(s: NotifySettings): Promise<void> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT", headers: jsonAuthHeaders(), body: JSON.stringify(s),
  });
  check401(res);
  if (!res.ok) throw new Error("儲存設定失敗");
}

export async function testNotify(): Promise<{ results: Record<string, { ok: boolean; msg: string }> }> {
  const res = await fetch(`${API_BASE}/api/settings/test`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "測試失敗");
  return res.json();
}

// ---------- 排程 ----------

export interface Schedule {
  id: number;
  keywords: string[];
  provider: string;
  pages: number;
  max_detail: number;
  scrape_details: boolean;
  interval_hours: number;
  enabled: boolean;
  last_run: string | null;
}

export type ScheduleInput = Omit<Schedule, "id" | "last_run">;

export async function getSchedules(): Promise<{ schedules: Schedule[] }> {
  const res = await fetch(`${API_BASE}/api/schedules`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取排程失敗");
  return res.json();
}

export async function createSchedule(data: ScheduleInput): Promise<Schedule> {
  const res = await fetch(`${API_BASE}/api/schedules`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "建立排程失敗");
  return res.json();
}

export async function updateSchedule(id: number, data: ScheduleInput): Promise<Schedule> {
  const res = await fetch(`${API_BASE}/api/schedules/${id}`, {
    method: "PATCH", headers: jsonAuthHeaders(), body: JSON.stringify(data),
  });
  check401(res);
  if (!res.ok) throw new Error("更新排程失敗");
  return res.json();
}

export async function deleteSchedule(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/schedules/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除排程失敗");
}

export async function runSchedule(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/schedules/${id}/run`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("執行排程失敗");
}

// ---------- 監看(到貨/開賣通知)----------

export interface Watch {
  id: number;
  name: string;
  url: string;
  available_keywords: string[];
  unavailable_keywords: string[];
  interval_minutes: number;
  enabled: boolean;
  last_status: string;
  last_checked: string | null;
  target_price: number | null;
  last_price_twd?: number | null;
  mode?: string;
  notify_on?: string[];
  cta_text?: string;
  cta_url?: string;
}

export type WatchInput = Omit<Watch, "id" | "last_status" | "last_checked" | "last_price_twd">;

export async function getWatches(): Promise<{ watches: Watch[] }> {
  const res = await fetch(`${API_BASE}/api/watches`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取監看失敗");
  return res.json();
}

export async function createWatch(data: WatchInput): Promise<Watch> {
  const res = await fetch(`${API_BASE}/api/watches`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "建立監看失敗");
  return res.json();
}

export async function updateWatch(id: number, data: WatchInput): Promise<Watch> {
  const res = await fetch(`${API_BASE}/api/watches/${id}`, {
    method: "PATCH", headers: jsonAuthHeaders(), body: JSON.stringify(data),
  });
  check401(res);
  if (!res.ok) throw new Error("更新監看失敗");
  return res.json();
}

export async function deleteWatch(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/watches/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除監看失敗");
}

export async function checkWatch(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/watches/${id}/check`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("檢查失敗");
}

// ---------- 管理員 ----------

export interface AdminStats {
  total_users: number;
  total_ai_calls: number;
  total_runs: number;
  total_watches: number;
  total_schedules: number;
  total_posts: number;
  total_threads: number;
  total_replies: number;
  new_users_7d: number;
  by_provider: Record<string, number>;
  by_plan: Record<string, number>;
  top_ai_users: { email: string; ai_used: number }[];
}

export interface AdminUser {
  id: number;
  email: string;
  username?: string;
  provider: string;
  plan: string;
  privileged?: boolean;
  banned?: boolean;
  ai_used: number;
  tags?: string[];
  created_at: string | null;
}

export interface AdminCharts {
  signups: { date: string; count: number }[];
  ai_usage: { date: string; ai: number; search: number }[];
  content: { date: string; runs: number; posts: number }[];
}
export async function getAdminCharts(): Promise<AdminCharts> {
  const res = await fetch(`${API_BASE}/api/admin/charts`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取圖表失敗");
  return res.json();
}

export interface CrawlLog { id: string; user: string; email: string; mode: string; target: string; total: number; finished_at: string | null; }
export async function getAdminCrawls(): Promise<{ crawls: CrawlLog[] }> {
  const res = await fetch(`${API_BASE}/api/admin/crawls`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取爬取紀錄失敗");
  return res.json();
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await fetch(`${API_BASE}/api/admin/stats`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取統計失敗");
  return res.json();
}

export async function getAdminUsers(): Promise<{ users: AdminUser[] }> {
  const res = await fetch(`${API_BASE}/api/admin/users`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取使用者失敗");
  return res.json();
}

export interface AdminUserDetail extends AdminUser {
  admin_note: string;
  tags: string[];
  counts: { runs: number; watches: number; schedules: number; threads: number; favorites: number; posts: number; replies: number };
  recent_runs: { id: string; keywords: string[]; total: number; finished_at: string | null }[];
  channels: { discord: boolean; telegram: boolean; own_ai_keys: boolean; daily_digest: boolean };
  watches: { id: number; name: string; url: string; last_status: string; interval_minutes: number; enabled: boolean; target_price: number | null }[];
  schedules: { id: number; keywords: string[]; interval_hours: number; enabled: boolean; provider: string; last_run: string | null }[];
  ai_cost: number;
  ai_chats: { id: number; kind: string; question: string; answer: string; created_at: string | null }[];
}

export async function getAdminRun(runId: string): Promise<{ keywords: string[]; summary: CrawlResult["summary"]; records: CrawlResult["records"] }> {
  const res = await fetch(`${API_BASE}/api/admin/run/${runId}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取搜尋結果失敗");
  return res.json();
}

export async function getAdminUserDetail(id: number): Promise<AdminUserDetail> {
  const res = await fetch(`${API_BASE}/api/admin/users/${id}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取使用者失敗");
  return res.json();
}

export async function setUserNote(id: number, admin_note: string, tags: string[]): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/users/${id}/note`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ admin_note, tags }),
  });
  check401(res);
  if (!res.ok) throw new Error("儲存備註失敗");
}

export async function setUserPlan(userId: number, plan: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/users/${userId}/plan`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ plan }),
  });
  check401(res);
  if (!res.ok) throw new Error("更新方案失敗");
}

export async function setUserPrivilege(userId: number, privileged: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/users/${userId}/privilege`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ privileged }),
  });
  check401(res);
  if (!res.ok) throw new Error("更新特權失敗");
}

export async function createBindCode(): Promise<{ code: string }> {
  const res = await fetch(`${API_BASE}/api/bind/code`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("產生綁定碼失敗");
  return res.json();
}

export async function updateProfile(username: string): Promise<{ username: string }> {
  const res = await fetch(`${API_BASE}/api/auth/profile`, {
    method: "PATCH", headers: jsonAuthHeaders(), body: JSON.stringify({ username }),
  });
  check401(res);
  if (!res.ok) throw new Error("更新名稱失敗");
  return res.json();
}

export async function setUserBanned(userId: number, banned: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/users/${userId}/ban`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ banned }),
  });
  check401(res);
  if (!res.ok) throw new Error("更新停權失敗");
}

export function exportUsersUrl(): string {
  return `${API_BASE}/api/admin/users/export`;
}

export async function sendBroadcast(data: { title: string; body: string; url: string; channels: string[]; segment?: string; run_at?: string | null }): Promise<{ ok: boolean; scheduled?: boolean; recipients?: number; inapp?: number; tg?: number; discord?: number; email?: number }> {
  const res = await fetch(`${API_BASE}/api/admin/broadcast`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("發送失敗");
  return res.json();
}
export interface ScheduledBroadcast { id: number; title: string; segment: string; channels: string[]; run_at: string | null; sent: boolean; result: Record<string, number>; }
export async function getScheduledBroadcasts(): Promise<{ items: ScheduledBroadcast[] }> {
  const res = await fetch(`${API_BASE}/api/admin/broadcasts/scheduled`, { headers: authHeaders() });
  check401(res); if (!res.ok) throw new Error("讀取失敗"); return res.json();
}
export async function deleteScheduledBroadcast(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/broadcasts/scheduled/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res); if (!res.ok) throw new Error("刪除失敗");
}

export interface KpiReport {
  totals: { users: number; new_users: number; searches: number; dau: number; wau: number; mau: number };
  funnel: { step: string; count: number }[];
  daily: { date: string; signups: number; searches: number; active: number }[];
  days: number;
}
export async function getRunItems(runId: string, offset = 0, limit = 500): Promise<{ items: CrawlResult["records"]; total: number }> {
  const res = await fetch(`${API_BASE}/api/run/${runId}/items?offset=${offset}&limit=${limit}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取完整資料失敗");
  return res.json();
}

export async function getEnvCheck(): Promise<{ groups: Record<string, Record<string, boolean>> }> {
  const res = await fetch(`${API_BASE}/api/admin/env-check`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取環境檢查失敗");
  return res.json();
}

export async function getKpi(days = 30): Promise<KpiReport> {
  const res = await fetch(`${API_BASE}/api/admin/kpi?days=${days}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取 KPI 失敗");
  return res.json();
}
export function kpiExportUrl(days = 30): string { return `${API_BASE}/api/admin/kpi/export?days=${days}`; }

export interface AuditLog { id: number; admin_email: string; action: string; target_type?: string; target: string; detail: string; ip?: string; changes?: Record<string, unknown>; created_at: string | null; }
export interface AuditFilter { page?: number; action?: string; actor?: string; date_from?: string; date_to?: string; }
export async function getAuditLogs(f: AuditFilter = {}): Promise<{ logs: AuditLog[]; total: number; page: number; per: number; actions: string[] }> {
  const p = new URLSearchParams();
  if (f.page) p.set("page", String(f.page));
  if (f.action) p.set("action", f.action);
  if (f.actor) p.set("actor", f.actor);
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  const res = await fetch(`${API_BASE}/api/admin/audit?${p.toString()}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取稽核失敗");
  return res.json();
}
export function auditExportUrl(f: AuditFilter = {}): string {
  const p = new URLSearchParams();
  if (f.action) p.set("action", f.action);
  if (f.actor) p.set("actor", f.actor);
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  return `${API_BASE}/api/admin/audit/export?${p.toString()}`;
}

export interface Announcement { id: number; title: string; body: string; level: string; active: boolean; created_at: string | null; }
export async function getAnnouncements(): Promise<{ announcements: Announcement[] }> {
  const res = await fetch(`${API_BASE}/api/announcements`);
  if (!res.ok) return { announcements: [] };
  return res.json();
}
export async function adminListAnnouncements(): Promise<{ announcements: Announcement[] }> {
  const res = await fetch(`${API_BASE}/api/admin/announcements`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取公告失敗");
  return res.json();
}
export async function adminCreateAnnouncement(data: { title: string; body: string; level: string; active: boolean }): Promise<Announcement> {
  const res = await fetch(`${API_BASE}/api/admin/announcements`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("建立公告失敗");
  return res.json();
}
export async function adminDeleteAnnouncement(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/announcements/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除公告失敗");
}

export async function adminEmailBlast(subject: string, body: string): Promise<{ sent: number; total: number }> {
  const res = await fetch(`${API_BASE}/api/admin/email-blast`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ subject, body }) });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "群發失敗");
  return res.json();
}

export interface ReportItem { id: number; target_type: string; target_id: number; reason: string; reporter_id: number; status: string; created_at: string | null; }
export async function createReport(target_type: string, target_id: number, reason: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/report`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ target_type, target_id, reason }) });
  check401(res);
  if (!res.ok) throw new Error("檢舉失敗");
}
export async function getReports(status = "open"): Promise<{ reports: ReportItem[] }> {
  const res = await fetch(`${API_BASE}/api/admin/reports?status=${status}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取檢舉失敗");
  return res.json();
}
export async function resolveReport(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/reports/${id}/resolve`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("處理失敗");
}

export async function getSeo(): Promise<Record<string, string>> {
  const res = await fetch(`${API_BASE}/api/seo`);
  if (!res.ok) return {};
  return res.json();
}
export async function saveSeo(data: Record<string, string>): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/seo`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("儲存 SEO 失敗");
}

export interface AiCosts {
  total_cost: number; total_in: number; total_out: number;
  by_model: { model: string; calls: number; cost: number }[];
  recent: { email: string; provider: string; model: string; in_tokens: number; out_tokens: number; cost: number; created_at: string | null }[];
  top_users: { email: string; cost: number }[];
  trend?: { date: string; cost: number }[];
}
export async function getAiCosts(): Promise<AiCosts> {
  const res = await fetch(`${API_BASE}/api/admin/ai-costs`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取 AI 成本失敗");
  return res.json();
}

export interface DeepInsights {
  total: number;
  price_stats: { count: number; min: number; max: number; median: number; avg: number; p25: number; p75: number } | Record<string, never>;
  histogram: { range: string; count: number }[];
  good_deals: { title: string; price_twd: number; discount_pct: number; url: string; domain: string; status: string }[];
  outliers: { title: string; reason: string; price_twd: number; url: string; domain: string }[];
  clusters: { title: string; count: number; domains: string[]; min_twd: number | null; cheapest_url: string; cheapest_domain: string }[];
  status_dist: Record<string, number>;
  trust_dist: Record<string, number>;
  cheapest: { title: string; price_twd: number; url: string; domain: string } | null;
  best_value: { title: string; price_twd: number; deal_score: number; url: string; domain: string } | null;
  vertical?: string;
  headline?: string;
  facets?: InsightFacet[];
}
export interface InsightFacet {
  type: "dist" | "range" | "stat";
  label: string;
  items?: { name: string; count: number }[];
  unit?: string; min?: number; max?: number; median?: number; count?: number;
  value?: string | number;
}
export interface RunCompare {
  has_previous: boolean; prev_date?: string | null;
  cheaper?: { title: string; now: number; was: number; diff: number }[];
  pricier?: { title: string; now: number; was: number; diff: number }[];
  new_items?: string[]; gone?: string[];
}
export async function getRunCompare(runId: string): Promise<RunCompare> {
  const res = await fetch(`${API_BASE}/api/insights/compare/${runId}`);
  if (!res.ok) return { has_previous: false };
  return res.json();
}
export interface InsightEntity { title: string; url: string; price_twd: number | null; domain: string; note: string; }
export async function getAiInsight(runId: string, vertical = ""): Promise<{ insight: string; model: string; entities: InsightEntity[] }> {
  const res = await fetch(`${API_BASE}/api/insights/ai`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ run_id: runId, vertical }) });
  if (!res.ok) throw new Error("AI 洞察失敗"); return res.json();
}
export async function aiMetaPost(title: string, content: string): Promise<{ seo_title: string; excerpt: string; tags: string[] }> {
  const res = await fetch(`${API_BASE}/api/blog/ai-meta`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ title, content }) });
  check401(res); if (!res.ok) throw new Error("AI 產生 SEO 失敗"); return res.json();
}
export async function aiCoverPost(title: string, style = "插畫"): Promise<{ url: string }> {
  const res = await fetch(`${API_BASE}/api/blog/ai-cover`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ title, style }) });
  check401(res); if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "封面生成失敗"); return res.json();
}
export async function getPreviewToken(postId: number): Promise<{ token: string }> {
  const res = await fetch(`${API_BASE}/api/blog/manage/${postId}/preview-token`, { method: "POST", headers: authHeaders() });
  check401(res); if (!res.ok) throw new Error("取得預覽連結失敗"); return res.json();
}

export async function getInsights(runId?: string, records?: unknown[], vertical = ""): Promise<DeepInsights> {
  const res = await fetch(`${API_BASE}/api/insights`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(runId ? { run_id: runId, vertical } : { records, vertical }),
  });
  if (!res.ok) throw new Error("分析失敗");
  return res.json();
}

export interface AiProviderConfig { model: string; enabled: boolean; has_key: boolean; key_hint?: string; }
export interface AiConfig { default_provider: string; providers: Record<string, AiProviderConfig>; }
export async function getAiConfig(): Promise<AiConfig> {
  const res = await fetch(`${API_BASE}/api/admin/ai-config`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取 AI 設定失敗");
  return res.json();
}
export async function saveAiConfig(provider: string, data: { key?: string; model?: string; enabled?: boolean }): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/ai-config`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ provider, ...data }) });
  check401(res);
  if (!res.ok) throw new Error("儲存失敗");
}
export async function setAiDefault(provider: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/ai-config/default`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ provider }) });
  check401(res);
  if (!res.ok) throw new Error("儲存失敗");
}
export async function testAiProvider(provider: string, key?: string): Promise<{ ok: boolean; error?: string; model?: string }> {
  const res = await fetch(`${API_BASE}/api/admin/ai-config/test`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ provider, key }) });
  check401(res);
  return res.json();
}

export interface BotChat { id: number; platform: string; platform_user: string; question: string; answer: string; created_at: string | null; }
export async function getBotChats(): Promise<{ chats: BotChat[] }> {
  const res = await fetch(`${API_BASE}/api/admin/bot-chats`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取 Bot 對話失敗");
  return res.json();
}

export async function getAppSettings(): Promise<{ settings: Record<string, string> }> {
  const res = await fetch(`${API_BASE}/api/admin/app-settings`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取應用設定失敗");
  return res.json();
}
export async function saveAppSetting(key: string, value: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/app-settings`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ key, value }) });
  check401(res);
  if (!res.ok) throw new Error("儲存應用設定失敗");
}

export interface PageSeo { path: string; title?: string; description?: string; keywords?: string; }
export async function listPageSeo(): Promise<{ pages: PageSeo[] }> {
  const res = await fetch(`${API_BASE}/api/admin/seo/pages`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取各頁 SEO 失敗");
  return res.json();
}
export async function savePageSeo(data: PageSeo): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/seo/page`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("儲存頁面 SEO 失敗");
}

export async function setupTelegramBot(): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/api/admin/telegram/setup`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("設定失敗");
  return res.json();
}

export async function setupDiscordBot(): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${API_BASE}/api/admin/discord/setup`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("設定失敗");
  return res.json();
}

// ---------- 部落格 ----------

export interface BlogPost {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  cover_image: string;
  category: string;
  tags: string[];
  published: boolean;
  featured?: boolean;
  likes?: number;
  liked?: boolean;
  views?: number;
  has_password?: boolean;
  locked?: boolean;
  content?: string;
  author?: string;
  author_id?: number;
  series?: string;
  comments?: BlogComment[];
  prev?: { slug: string; title: string } | null;
  next?: { slug: string; title: string } | null;
  related?: { slug: string; title: string; cover_image: string; likes: number }[];
  created_at: string | null;
  updated_at: string | null;
}

export interface BlogComment {
  id: number; post_id: number; author_id?: number; author_name: string;
  content: string; status: string; post_title?: string; parent_id?: number | null;
  like_count?: number; replies?: BlogComment[]; created_at: string | null;
}

export type PostInput = {
  title: string; slug: string; excerpt: string; content: string;
  cover_image: string; category: string; series: string; tags: string[]; published: boolean; featured?: boolean; password?: string;
};

export async function likeComment(commentId: number): Promise<{ liked: boolean; like_count: number }> {
  const res = await fetch(`${API_BASE}/api/blog/comment/${commentId}/like`, { method: "POST", headers: authHeaders() });
  check401(res); if (!res.ok) throw new Error("操作失敗"); return res.json();
}
export async function getReactions(postId: number): Promise<{ counts: Record<string, number>; mine: string[] }> {
  const res = await fetch(`${API_BASE}/api/blog/${postId}/reactions`, { headers: authHeaders() });
  if (!res.ok) return { counts: {}, mine: [] }; return res.json();
}
export async function toggleReaction(postId: number, emoji: string): Promise<{ counts: Record<string, number>; mine: string[] }> {
  const res = await fetch(`${API_BASE}/api/blog/${postId}/reactions`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ emoji }) });
  check401(res); if (!res.ok) throw new Error("操作失敗"); return res.json();
}
export async function unlockPost(postId: number, password: string): Promise<{ content: string }> {
  const res = await fetch(`${API_BASE}/api/blog/${postId}/unlock`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
  if (!res.ok) throw new Error("密碼錯誤"); return res.json();
}
export async function incrementView(postId: number): Promise<void> {
  try { await fetch(`${API_BASE}/api/blog/${postId}/view`, { method: "POST" }); } catch { /* */ }
}
export async function aiWritePost(mode: "full" | "outline" | "refine", topic: string, content = ""): Promise<{ content: string; model: string }> {
  const res = await fetch(`${API_BASE}/api/blog/ai-write`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ mode, topic, content }) });
  check401(res); if (!res.ok) throw new Error("AI 產生失敗"); return res.json();
}

export async function getBlogTaxonomy(): Promise<{ categories: { name: string; count: number }[]; tags: { name: string; count: number }[] }> {
  const res = await fetch(`${API_BASE}/api/blog-taxonomy`);
  if (!res.ok) return { categories: [], tags: [] };
  return res.json();
}
export async function likeBlogPost(postId: number): Promise<{ liked: boolean; likes: number }> {
  const res = await fetch(`${API_BASE}/api/blog/${postId}/like`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("操作失敗");
  return res.json();
}
export async function addBlogComment(postId: number, content: string, parent_id?: number | null): Promise<BlogComment> {
  const res = await fetch(`${API_BASE}/api/blog/${postId}/comments`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ content, parent_id: parent_id ?? null }) });
  check401(res);
  if (!res.ok) throw new Error("留言失敗");
  return res.json();
}
export async function adminListComments(): Promise<{ comments: BlogComment[] }> {
  const res = await fetch(`${API_BASE}/api/admin/comments`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取留言失敗");
  return res.json();
}
export async function setCommentStatus(id: number, status: "visible" | "hidden" | "delete"): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/comments/${id}/status`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ status }) });
  check401(res);
  if (!res.ok) throw new Error("操作失敗");
}
export async function setPostFeatured(id: number, featured: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/blog/${id}/featured`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ featured }) });
  check401(res);
  if (!res.ok) throw new Error("操作失敗");
}

export async function subscribeAuthor(authorId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/blog/author/${authorId}/subscribe`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("訂閱失敗");
}
export async function unsubscribeAuthor(authorId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/blog/author/${authorId}/subscribe`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("取消訂閱失敗");
}
export async function isSubscribed(authorId: number): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/blog/author/${authorId}/subscribed`, { headers: authHeaders() });
  if (!res.ok) return false;
  return (await res.json()).subscribed;
}

export async function adminListPosts(): Promise<{ posts: BlogPost[] }> {
  const res = await fetch(`${API_BASE}/api/admin/blog`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取文章失敗");
  return res.json();
}

export async function adminGetPost(id: number): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/api/admin/blog/${id}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取文章失敗");
  return res.json();
}

export async function createPost(data: PostInput): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/api/admin/blog`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data),
  });
  check401(res);
  if (!res.ok) throw new Error("建立文章失敗");
  return res.json();
}

export async function updatePost(id: number, data: PostInput): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/api/admin/blog/${id}`, {
    method: "PUT", headers: jsonAuthHeaders(), body: JSON.stringify(data),
  });
  check401(res);
  if (!res.ok) throw new Error("更新文章失敗");
  return res.json();
}

export async function deletePost(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/blog/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除文章失敗");
}

// ---- Web Push ----
export async function getPushKey(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/push/key`);
  if (!res.ok) return "";
  return (await res.json()).key || "";
}
export async function subscribePush(sub: PushSubscription): Promise<void> {
  await fetch(`${API_BASE}/api/push/subscribe`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(sub) });
}
export async function unsubscribePush(endpoint: string): Promise<void> {
  await fetch(`${API_BASE}/api/push/unsubscribe`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ endpoint }) });
}

// ---- 站內通知 ----
export interface Notif { id: number; title: string; body: string; url: string; read: boolean; created_at: string | null; }
export async function getNotifications(): Promise<{ items: Notif[]; unread: number }> {
  const res = await fetch(`${API_BASE}/api/notifications`, { headers: authHeaders() });
  if (!res.ok) return { items: [], unread: 0 };
  return res.json();
}
export async function markNotificationsRead(): Promise<void> {
  await fetch(`${API_BASE}/api/notifications/read`, { method: "POST", headers: authHeaders() }).catch(() => {});
}

// ---- Email 驗證 ----
export async function verifyEmail(token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/verify-email`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "驗證失敗");
}

export async function resendVerify(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth/resend-verify`, { method: "POST", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "重寄失敗");
}

// ---- 額度 ----
export interface Quota { unlimited: boolean; ai_used: number; search_used: number; ai_limit: number; search_limit: number; }
export async function getQuota(): Promise<Quota> {
  const res = await fetch(`${API_BASE}/api/quota`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取額度失敗");
  return res.json();
}

// ---- 分享連結 ----
export async function setRunShared(runId: string, shared: boolean): Promise<{ shared: boolean }> {
  const res = await fetch(`${API_BASE}/api/history/${runId}/share`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ shared }),
  });
  check401(res);
  if (!res.ok) throw new Error("設定分享失敗");
  return res.json();
}

export async function getSharedRun(runId: string): Promise<{ id: string; keywords: string[]; summary: CrawlResult["summary"]; records: CrawlResult["records"] }> {
  const res = await fetch(`${API_BASE}/api/share/${runId}`);
  if (!res.ok) throw new Error("這個分享連結不存在或已關閉");
  return res.json();
}

// ---- 使用者自己的部落格 ----
export async function getMyPosts(): Promise<{ posts: BlogPost[] }> {
  const res = await fetch(`${API_BASE}/api/blog/mine`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取我的文章失敗");
  return res.json();
}

export async function getMyPost(id: number): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/api/blog/manage/${id}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取文章失敗");
  return res.json();
}

export async function myCreatePost(data: PostInput): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/api/blog`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("建立文章失敗");
  return res.json();
}

export async function myUpdatePost(id: number, data: PostInput): Promise<BlogPost> {
  const res = await fetch(`${API_BASE}/api/blog/${id}`, { method: "PUT", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("更新文章失敗");
  return res.json();
}

export async function myDeletePost(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/blog/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除文章失敗");
}

// ---------- 收藏 / 價格走勢 ----------

export interface Favorite {
  id: number; url: string; title: string; image_url: string; domain: string;
  price: string; target_twd: number | null; created_at: string | null;
}

export async function getFavorites(): Promise<{ favorites: Favorite[]; urls: string[] }> {
  const res = await fetch(`${API_BASE}/api/favorites`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取收藏失敗");
  return res.json();
}

export async function addFavorite(data: { url: string; title?: string; image_url?: string; domain?: string; price?: string }): Promise<Favorite> {
  const res = await fetch(`${API_BASE}/api/favorites`, { method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify(data) });
  check401(res);
  if (!res.ok) throw new Error("收藏失敗");
  return res.json();
}

export async function setFavoriteTarget(id: number, target_twd: number | null): Promise<Favorite> {
  const res = await fetch(`${API_BASE}/api/favorites/${id}`, { method: "PATCH", headers: jsonAuthHeaders(), body: JSON.stringify({ target_twd }) });
  check401(res);
  if (!res.ok) throw new Error("設定失敗");
  return res.json();
}

export async function removeFavorite(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/favorites/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("移除失敗");
}

export async function getPriceHistory(url: string): Promise<{ history: { date: string; price_twd: number; price: string }[] }> {
  const res = await fetch(`${API_BASE}/api/price-history?url=${encodeURIComponent(url)}`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取走勢失敗");
  return res.json();
}

// ---------- 討論區 ----------

export interface ForumCategory { slug: string; label: string; emoji: string; }
export interface ForumThread {
  id: number; category: string; title: string; author: string; author_id: number;
  reply_count: number; likes?: number; created_at: string | null; last_reply_at: string | null;
  content?: string; replies?: ForumReply[];
}

export async function likeThread(id: number): Promise<{ likes: number }> {
  const res = await fetch(`${API_BASE}/api/forum/threads/${id}/like`, { method: "POST" });
  if (!res.ok) throw new Error("按讚失敗");
  return res.json();
}
export interface ForumReply { id: number; content: string; author: string; author_id: number; created_at: string | null; }

export async function getForumCategories(): Promise<{ categories: ForumCategory[] }> {
  const res = await fetch(`${API_BASE}/api/forum/categories`);
  if (!res.ok) throw new Error("讀取分類失敗");
  return res.json();
}

export async function getForumThreads(category?: string): Promise<{ threads: ForumThread[] }> {
  const q = category ? `?category=${encodeURIComponent(category)}` : "";
  const res = await fetch(`${API_BASE}/api/forum/threads${q}`);
  if (!res.ok) throw new Error("讀取主題失敗");
  return res.json();
}

export async function getForumThread(id: number): Promise<ForumThread> {
  const res = await fetch(`${API_BASE}/api/forum/threads/${id}`);
  if (!res.ok) throw new Error("讀取主題失敗");
  return res.json();
}

export async function createThread(category: string, title: string, content: string): Promise<ForumThread> {
  const res = await fetch(`${API_BASE}/api/forum/threads`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ category, title, content }),
  });
  check401(res);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "發表失敗");
  return res.json();
}

export async function createReply(threadId: number, content: string): Promise<ForumReply> {
  const res = await fetch(`${API_BASE}/api/forum/threads/${threadId}/replies`, {
    method: "POST", headers: jsonAuthHeaders(), body: JSON.stringify({ content }),
  });
  check401(res);
  if (!res.ok) throw new Error("回覆失敗");
  return res.json();
}

export async function deleteThread(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/forum/threads/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除失敗");
}

export async function deleteReply(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/forum/replies/${id}`, { method: "DELETE", headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("刪除失敗");
}
