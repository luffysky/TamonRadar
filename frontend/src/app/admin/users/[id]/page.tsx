"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAdminUserDetail, setUserNote, setUserPlan, type AdminUserDetail } from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";

export default function AdminUserDetailPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [u, setU] = useState<AdminUserDetail | null>(null);
  const [note, setNote] = useState("");
  const [tags, setTags] = useState("");

  async function load() {
    const d = await getAdminUserDetail(id);
    setU(d);
    setNote(d.admin_note);
    setTags((d.tags || []).join(", "));
  }
  useEffect(() => { if (user) load().catch(() => {}); /* eslint-disable-next-line */ }, [user, id]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;
  if (!u) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  async function saveNote() {
    const t = tags.split(",").map((x) => x.trim()).filter(Boolean);
    await setUserNote(id, note, t);
    toast("已儲存備註", "success");
    load();
  }
  async function togglePlan() {
    await setUserPlan(id, u!.plan === "pro" ? "free" : "pro");
    toast("方案已更新", "success");
    load();
  }

  const Stat = ({ label, value }: { label: string; value: number }) => (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-center dark:border-slate-700 dark:bg-slate-800">
      <div className="text-lg font-bold text-brand-600 dark:text-brand-300">{value}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Link href="/admin" className="text-sm text-brand-600 hover:underline dark:text-brand-300">← 回管理後台</Link>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h1 className="text-lg font-bold text-slate-800 dark:text-slate-100">{u.email}</h1>
        <p className="mt-1 text-xs text-slate-400">
          #{u.id} · {u.provider} · 註冊 {u.created_at ? new Date(u.created_at).toLocaleString("zh-TW") : "-"}
        </p>
        <div className="mt-3 flex items-center gap-3">
          <span className={`rounded-full px-2 py-0.5 text-xs ${u.plan === "pro" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"}`}>{u.plan}</span>
          <button onClick={togglePlan} className="rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">
            {u.plan === "pro" ? "降為 free" : "升為 pro"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="搜尋" value={u.counts.runs} />
        <Stat label="監看" value={u.counts.watches} />
        <Stat label="排程" value={u.counts.schedules} />
        <Stat label="發文" value={u.counts.threads} />
        <Stat label="AI 用量" value={u.ai_used} />
      </div>

      <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">標籤(逗號分隔)</label>
        <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="例:VIP, 早期使用者" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600" />
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">後台備註</label>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600" />
        <button onClick={saveNote} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">儲存</button>
      </div>
    </div>
  );
}
