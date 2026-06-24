"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { ADMIN_BASE } from "@/lib/admin";
import {
  adminListAnnouncements, adminCreateAnnouncement, adminDeleteAnnouncement,
  getAuditLogs, getReports, resolveReport, adminEmailBlast, getSeo, saveSeo, exportUsersUrl,
  listPageSeo, savePageSeo, getAppSettings, saveAppSetting, getAiCosts, getBotChats,
  adminListComments, setCommentStatus,
  type Announcement, type AuditLog, type ReportItem, type PageSeo, type AiCosts, type BotChat, type BlogComment,
} from "@/lib/api";

export default function AdminOpsPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [tab, setTab] = useState<"ann" | "audit" | "report" | "email" | "seo" | "app" | "ai" | "bot" | "mod">("ann");

  const [anns, setAnns] = useState<Announcement[]>([]);
  const [annForm, setAnnForm] = useState({ title: "", body: "", level: "info", active: true });
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [emailForm, setEmailForm] = useState({ subject: "", body: "" });
  const [seo, setSeo] = useState<Record<string, string>>({});
  const [pages, setPages] = useState<PageSeo[]>([]);
  const [pageForm, setPageForm] = useState<PageSeo>({ path: "/", title: "", description: "", keywords: "" });
  const [appSettings, setAppSettings] = useState<Record<string, string>>({});
  const [appForm, setAppForm] = useState({ key: "", value: "" });
  const [aiCosts, setAiCosts] = useState<AiCosts | null>(null);
  const [botChats, setBotChats] = useState<BotChat[]>([]);
  const [botPlatform, setBotPlatform] = useState("");
  const [botQuery, setBotQuery] = useState("");
  const [comments, setComments] = useState<BlogComment[]>([]);
  const [modQuery, setModQuery] = useState("");

  useEffect(() => {
    if (!user) return;
    adminListAnnouncements().then((d) => setAnns(d.announcements)).catch(() => {});
    getAuditLogs().then((d) => setLogs(d.logs)).catch(() => {});
    getReports().then((d) => setReports(d.reports)).catch(() => {});
    getSeo().then(setSeo).catch(() => {});
    listPageSeo().then((d) => setPages(d.pages)).catch(() => {});
    getAppSettings().then((d) => setAppSettings(d.settings)).catch(() => {});
    getAiCosts().then(setAiCosts).catch(() => {});
    getBotChats().then((d) => setBotChats(d.chats)).catch(() => {});
    adminListComments().then((d) => setComments(d.comments)).catch(() => {});
  }, [user]);

  async function moderate(id: number, status: "visible" | "hidden" | "delete") {
    try {
      await setCommentStatus(id, status);
      if (status === "delete") setComments((cs) => cs.filter((c) => c.id !== id));
      else setComments((cs) => cs.map((c) => (c.id === id ? { ...c, status } : c)));
    } catch { /* */ }
  }

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900";
  const tabs: [typeof tab, string][] = [["ann", "站內公告"], ["audit", "稽核日誌"], ["report", "檢舉佇列"], ["email", "Email 群發"], ["seo", "SEO"], ["app", "應用設定"], ["ai", "AI 成本"], ["bot", "Bot 對話"], ["mod", "留言審核"]];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">營運管理</h1>
        <div className="flex gap-2">
          <a href={exportUsersUrl()} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">匯出使用者 CSV</a>
          <Link href={ADMIN_BASE} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">← 後台</Link>
        </div>
      </div>

      <div className="scroll-thin flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-700">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className={`shrink-0 whitespace-nowrap px-3 py-2 text-sm ${tab === k ? "border-b-2 border-brand-600 font-medium text-brand-600 dark:text-brand-300" : "text-slate-500"}`}>{label}</button>
        ))}
      </div>

      {tab === "ann" && (
        <div className="space-y-3">
          <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <input value={annForm.title} onChange={(e) => setAnnForm({ ...annForm, title: e.target.value })} placeholder="公告標題" className={field} />
            <textarea value={annForm.body} onChange={(e) => setAnnForm({ ...annForm, body: e.target.value })} placeholder="內容" rows={3} className={field} />
            <div className="flex items-center gap-2">
              <select value={annForm.level} onChange={(e) => setAnnForm({ ...annForm, level: e.target.value })} className={field + " max-w-[140px]"}>
                <option value="info">資訊</option><option value="success">成功</option><option value="warning">警告</option>
              </select>
              <button onClick={async () => { await adminCreateAnnouncement(annForm); setAnnForm({ title: "", body: "", level: "info", active: true }); toast("已發佈公告", "success"); adminListAnnouncements().then((d) => setAnns(d.announcements)); }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">發佈(推給所有人)</button>
            </div>
          </div>
          {anns.map((a) => (
            <div key={a.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-800">
              <div><span className="font-medium text-slate-700 dark:text-slate-200">{a.title}</span> <span className="text-xs text-slate-400">{a.level} · {a.active ? "顯示中" : "停用"}</span></div>
              <button onClick={async () => { await adminDeleteAnnouncement(a.id); toast("已刪除", "info"); adminListAnnouncements().then((d) => setAnns(d.announcements)); }} className="text-xs text-rose-600 hover:underline">刪除</button>
            </div>
          ))}
        </div>
      )}

      {tab === "audit" && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
          {logs.length === 0 ? <p className="p-4 text-slate-400">尚無紀錄</p> : logs.map((l) => (
            <div key={l.id} className="flex flex-wrap items-center gap-x-3 border-b border-slate-100 px-3 py-2 dark:border-slate-700">
              <span className="text-xs text-slate-400">{l.created_at ? new Date(l.created_at).toLocaleString("zh-TW") : ""}</span>
              <span className="font-medium text-brand-600 dark:text-brand-300">{l.action}</span>
              <span className="text-slate-600 dark:text-slate-300">{l.target} {l.detail}</span>
              <span className="ml-auto text-xs text-slate-400">{l.admin_email}</span>
            </div>
          ))}
        </div>
      )}

      {tab === "report" && (
        <div className="space-y-2">
          {reports.length === 0 ? <p className="text-sm text-slate-400">沒有待處理檢舉</p> : reports.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-800">
              <div>
                <span className="font-medium text-slate-700 dark:text-slate-200">{r.target_type} #{r.target_id}</span>
                <p className="text-xs text-slate-500">{r.reason || "(無理由)"} · 檢舉者 #{r.reporter_id}</p>
              </div>
              <button onClick={async () => { await resolveReport(r.id); toast("已處理", "success"); getReports().then((d) => setReports(d.reports)); }} className="rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">標記處理</button>
            </div>
          ))}
        </div>
      )}

      {tab === "email" && (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <p className="text-xs text-slate-400">寄給所有未停權、有 email 的使用者(需設定 Resend / Gmail)。</p>
          <input value={emailForm.subject} onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })} placeholder="主旨" className={field} />
          <textarea value={emailForm.body} onChange={(e) => setEmailForm({ ...emailForm, body: e.target.value })} placeholder="內容" rows={6} className={field} />
          <button onClick={async () => { if (!confirm("確定群發給所有使用者?")) return; try { const r = await adminEmailBlast(emailForm.subject, emailForm.body); toast(`已寄出 ${r.sent}/${r.total}`, "success"); } catch (e) { toast(e instanceof Error ? e.message : "失敗", "error"); } }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">送出群發</button>
        </div>
      )}

      {tab === "seo" && (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <label className="block text-sm text-slate-600 dark:text-slate-300">網站標題</label>
          <input value={seo.site_title ?? ""} onChange={(e) => setSeo({ ...seo, site_title: e.target.value })} className={field} />
          <label className="block text-sm text-slate-600 dark:text-slate-300">網站描述</label>
          <textarea value={seo.site_description ?? ""} onChange={(e) => setSeo({ ...seo, site_description: e.target.value })} rows={3} className={field} />
          <label className="block text-sm text-slate-600 dark:text-slate-300">關鍵字(逗號分隔)</label>
          <input value={seo.keywords ?? ""} onChange={(e) => setSeo({ ...seo, keywords: e.target.value })} className={field} />
          <label className="block text-sm text-slate-600 dark:text-slate-300">預設 OG 圖網址</label>
          <input value={seo.og_image ?? ""} onChange={(e) => setSeo({ ...seo, og_image: e.target.value })} className={field} />
          <button onClick={async () => { await saveSeo(seo); toast("已儲存 SEO", "success"); }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">儲存全站預設</button>

          <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-700">
            <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">各頁 SEO(覆寫該頁)</h3>
            <select value={pageForm.path} onChange={(e) => setPageForm({ ...pageForm, path: e.target.value })} className={field}>
              {["/", "/about", "/blog", "/forum"].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <input value={pageForm.title ?? ""} onChange={(e) => setPageForm({ ...pageForm, title: e.target.value })} placeholder="頁面 title" className={`${field} mt-2`} />
            <textarea value={pageForm.description ?? ""} onChange={(e) => setPageForm({ ...pageForm, description: e.target.value })} placeholder="頁面 description" rows={2} className={`${field} mt-2`} />
            <input value={pageForm.keywords ?? ""} onChange={(e) => setPageForm({ ...pageForm, keywords: e.target.value })} placeholder="關鍵字(逗號分隔)" className={`${field} mt-2`} />
            <button onClick={async () => { await savePageSeo(pageForm); toast(`已儲存 ${pageForm.path} 的 SEO`, "success"); listPageSeo().then((d) => setPages(d.pages)); }} className="mt-2 rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">儲存此頁</button>
            {pages.length > 0 && (
              <div className="mt-3 space-y-1 text-xs text-slate-500 dark:text-slate-400">
                {pages.map((p) => (
                  <button key={p.path} onClick={() => setPageForm({ path: p.path, title: p.title ?? "", description: p.description ?? "", keywords: p.keywords ?? "" })} className="block w-full truncate text-left hover:text-brand-600">
                    {p.path}:{p.title || "(無 title)"}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "ai" && aiCosts && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="text-2xl font-bold text-brand-600 dark:text-brand-300">${aiCosts.total_cost}</div>
              <div className="text-xs text-slate-500">總成本(USD)</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="text-2xl font-bold text-slate-700 dark:text-slate-200">{aiCosts.total_in.toLocaleString()}</div>
              <div className="text-xs text-slate-500">輸入 tokens</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="text-2xl font-bold text-slate-700 dark:text-slate-200">{aiCosts.total_out.toLocaleString()}</div>
              <div className="text-xs text-slate-500">輸出 tokens</div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">各模型成本</p>
              {aiCosts.by_model.length === 0 ? <p className="text-slate-400">尚無資料</p> : aiCosts.by_model.map((m) => (
                <div key={m.model} className="flex justify-between text-slate-600 dark:text-slate-300"><span className="truncate">{m.model}({m.calls})</span><span>${m.cost}</span></div>
              ))}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">成本前幾名使用者</p>
              {aiCosts.top_users.map((u) => (
                <div key={u.email} className="flex justify-between text-slate-600 dark:text-slate-300"><span className="truncate">{u.email}</span><span>${u.cost}</span></div>
              ))}
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <p className="border-b border-slate-100 px-3 py-2 font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200">最近呼叫明細</p>
            {aiCosts.recent.length === 0 ? <p className="p-3 text-slate-400">尚無資料</p> : aiCosts.recent.map((r, i) => (
              <div key={i} className="flex flex-wrap items-center gap-x-3 border-b border-slate-100 px-3 py-1.5 text-xs dark:border-slate-700">
                <span className="text-slate-400">{r.created_at ? new Date(r.created_at).toLocaleString("zh-TW") : ""}</span>
                <span className="text-slate-600 dark:text-slate-300">{r.model}</span>
                <span className="text-slate-400">in {r.in_tokens} / out {r.out_tokens}</span>
                <span className="ml-auto font-medium text-brand-600 dark:text-brand-300">${r.cost}</span>
                <span className="w-full truncate text-slate-400">{r.email}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "bot" && (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <p className="text-xs text-slate-400">使用者在 Telegram / Discord 跟 AI bot 的對話紀錄。</p>
          <div className="flex flex-wrap gap-2">
            <select value={botPlatform} onChange={(e) => setBotPlatform(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900">
              <option value="">全部平台</option>
              <option value="telegram">Telegram</option>
              <option value="discord">Discord</option>
            </select>
            <input value={botQuery} onChange={(e) => setBotQuery(e.target.value)} placeholder="搜尋使用者 / 問題 / 回答…" className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" />
          </div>
          {(() => {
            const q = botQuery.trim().toLowerCase();
            const filtered = botChats.filter((c) =>
              (!botPlatform || c.platform === botPlatform) &&
              (!q || `${c.platform_user} ${c.question} ${c.answer}`.toLowerCase().includes(q)));
            return filtered.length === 0 ? <p className="text-sm text-slate-400">無符合的紀錄</p> : filtered.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-100 p-2 text-sm dark:border-slate-700">
              <p className="text-[10px] text-slate-400">{c.platform} · {c.platform_user} · {c.created_at ? new Date(c.created_at).toLocaleString("zh-TW") : ""}</p>
              <p className="mt-0.5 font-medium text-slate-700 dark:text-slate-200">問:{c.question}</p>
              <p className="mt-0.5 whitespace-pre-wrap text-slate-600 dark:text-slate-300">答:{c.answer}</p>
            </div>
            ));
          })()}
        </div>
      )}

      {tab === "mod" && (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <input value={modQuery} onChange={(e) => setModQuery(e.target.value)} placeholder="搜尋留言 / 作者 / 文章…" className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900" />
          {(() => {
            const q = modQuery.trim().toLowerCase();
            const list = comments.filter((c) => !q || `${c.author_name} ${c.content} ${c.post_title}`.toLowerCase().includes(q));
            return list.length === 0 ? <p className="text-sm text-slate-400">沒有留言</p> : list.map((c) => (
              <div key={c.id} className={`rounded-lg border p-2 text-sm ${c.status === "hidden" ? "border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/30" : "border-slate-100 dark:border-slate-700"}`}>
                <p className="text-[10px] text-slate-400">{c.author_name} · 文章「{c.post_title}」· {c.created_at ? new Date(c.created_at).toLocaleString("zh-TW") : ""} · {c.status === "hidden" ? "已隱藏" : "顯示中"}</p>
                <p className="mt-0.5 whitespace-pre-wrap text-slate-700 dark:text-slate-200">{c.content}</p>
                <div className="mt-1.5 flex gap-2">
                  {c.status === "hidden"
                    ? <button onClick={() => moderate(c.id, "visible")} className="rounded border border-emerald-300 px-2 py-0.5 text-xs text-emerald-600 hover:bg-emerald-50">顯示</button>
                    : <button onClick={() => moderate(c.id, "hidden")} className="rounded border border-amber-300 px-2 py-0.5 text-xs text-amber-600 hover:bg-amber-50">隱藏</button>}
                  <button onClick={() => moderate(c.id, "delete")} className="rounded border border-rose-300 px-2 py-0.5 text-xs text-rose-600 hover:bg-rose-50">刪除</button>
                </div>
              </div>
            ));
          })()}
        </div>
      )}

      {tab === "app" && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <p className="text-xs text-slate-400">站台設定 / 功能旗標(key-value),例如聯絡信箱、維護模式等。</p>
          <div className="flex flex-wrap gap-2">
            <input value={appForm.key} onChange={(e) => setAppForm({ ...appForm, key: e.target.value })} placeholder="key" className={`${field} max-w-[200px]`} />
            <input value={appForm.value} onChange={(e) => setAppForm({ ...appForm, value: e.target.value })} placeholder="value" className={field + " flex-1"} />
            <button onClick={async () => { if (!appForm.key.trim()) return; await saveAppSetting(appForm.key.trim(), appForm.value); toast("已儲存", "success"); getAppSettings().then((d) => setAppSettings(d.settings)); setAppForm({ key: "", value: "" }); }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">儲存</button>
          </div>
          <div className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
            {Object.entries(appSettings).map(([k, v]) => (
              <button key={k} onClick={() => setAppForm({ key: k, value: v })} className="flex w-full items-center justify-between gap-3 py-2 text-left hover:opacity-80">
                <span className="shrink-0 font-mono text-xs text-brand-600 dark:text-brand-300">{k}</span>
                <span className="truncate text-slate-500 dark:text-slate-400">{v}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
