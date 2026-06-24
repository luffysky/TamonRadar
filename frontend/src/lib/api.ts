import type { CrawlResult, HistoryRun, ProgressEvent } from "./types";
import { authHeaders, clearSession, type AuthUser } from "./auth";

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

export interface AuditLog { id: number; admin_email: string; action: string; target: string; detail: string; created_at: string | null; }
export async function getAuditLogs(): Promise<{ logs: AuditLog[] }> {
  const res = await fetch(`${API_BASE}/api/admin/audit`, { headers: authHeaders() });
  check401(res);
  if (!res.ok) throw new Error("讀取稽核失敗");
  return res.json();
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
  content?: string;
  author?: string;
  author_id?: number;
  created_at: string | null;
  updated_at: string | null;
}

export type PostInput = {
  title: string; slug: string; excerpt: string; content: string;
  cover_image: string; category: string; tags: string[]; published: boolean;
};

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
