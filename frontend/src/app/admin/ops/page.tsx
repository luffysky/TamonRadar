"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { ADMIN_BASE } from "@/lib/admin";
import {
  adminListAnnouncements, adminCreateAnnouncement, adminDeleteAnnouncement,
  getAuditLogs, getReports, resolveReport, adminEmailBlast, getSeo, saveSeo, exportUsersUrl,
  type Announcement, type AuditLog, type ReportItem,
} from "@/lib/api";

export default function AdminOpsPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [tab, setTab] = useState<"ann" | "audit" | "report" | "email" | "seo">("ann");

  const [anns, setAnns] = useState<Announcement[]>([]);
  const [annForm, setAnnForm] = useState({ title: "", body: "", level: "info", active: true });
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [emailForm, setEmailForm] = useState({ subject: "", body: "" });
  const [seo, setSeo] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!user) return;
    adminListAnnouncements().then((d) => setAnns(d.announcements)).catch(() => {});
    getAuditLogs().then((d) => setLogs(d.logs)).catch(() => {});
    getReports().then((d) => setReports(d.reports)).catch(() => {});
    getSeo().then(setSeo).catch(() => {});
  }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900";
  const tabs: [typeof tab, string][] = [["ann", "站內公告"], ["audit", "稽核日誌"], ["report", "檢舉佇列"], ["email", "Email 群發"], ["seo", "SEO"]];

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
          <button onClick={async () => { await saveSeo(seo); toast("已儲存 SEO", "success"); }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">儲存</button>
        </div>
      )}
    </div>
  );
}
