"use client";

import { useEffect, useState } from "react";
import { Send, Clock, Trash2 } from "lucide-react";
import { useRequireAuth } from "@/components/AuthProvider";
import { sendBroadcast, getScheduledBroadcasts, deleteScheduledBroadcast, type ScheduledBroadcast } from "@/lib/api";

const CHANNELS: [string, string][] = [
  ["inapp", "站內通知 + 系統推播(Web Push)"],
  ["email", "Email"],
  ["tg", "Telegram(已設 chat id 者)"],
  ["discord", "Discord(已設 webhook / user id 者)"],
];
const SEGMENTS: [string, string][] = [
  ["all", "全體使用者"], ["privileged", "特權會員"], ["verified", "已驗證 Email"],
  ["telegram", "已設 Telegram"], ["discord", "已設 Discord"],
];

export default function AdminBroadcastsPage() {
  const { user, ready } = useRequireAuth();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const [channels, setChannels] = useState<string[]>(["inapp"]);
  const [segment, setSegment] = useState("all");
  const [runAt, setRunAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [scheduled, setScheduled] = useState<ScheduledBroadcast[]>([]);

  function loadScheduled() { getScheduledBroadcasts().then((d) => setScheduled(d.items)).catch(() => {}); }
  useEffect(() => { if (user) loadScheduled(); }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;

  function toggle(c: string) { setChannels((cs) => (cs.includes(c) ? cs.filter((x) => x !== c) : [...cs, c])); }
  async function send() {
    if (!title.trim()) { setResult("請填標題"); return; }
    if (channels.length === 0) { setResult("請至少選一個管道"); return; }
    const scheduledMode = !!runAt;
    if (!scheduledMode && !confirm(`確定立即發送「${title}」給【${SEGMENTS.find((s) => s[0] === segment)?.[1]}】?`)) return;
    setBusy(true); setResult(scheduledMode ? "排程中…" : "發送中…");
    try {
      const r = await sendBroadcast({ title, body, url, channels, segment, run_at: runAt ? new Date(runAt).toISOString() : null });
      if (r.scheduled) { setResult("✅ 已排程"); loadScheduled(); }
      else setResult(`✅ 已送達 ${r.recipients} 人:站內 ${r.inapp}、TG ${r.tg}、Discord ${r.discord}${r.email !== undefined ? `、Email ${r.email}` : ""}`);
      setTitle(""); setBody(""); setUrl(""); setRunAt("");
    } catch { setResult("❌ 發送失敗"); } finally { setBusy(false); }
  }

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900";

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">推播中心</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">一次把公告 / 活動推給指定分群,可多管道、可排程。</p>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="標題" className={field} />
        <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="內容" rows={5} className={field} />
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="連結(選填,通知可點)" className={field} />

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-slate-200">對象分群</span>
            <select value={segment} onChange={(e) => setSegment(e.target.value)} className={field}>
              {SEGMENTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium text-slate-700 dark:text-slate-200">排程時間(留空=立即)</span>
            <input type="datetime-local" value={runAt} onChange={(e) => setRunAt(e.target.value)} className={field} />
          </label>
        </div>

        <div className="space-y-1.5">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">發送管道</p>
          {CHANNELS.map(([k, l]) => (
            <label key={k} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              <input type="checkbox" checked={channels.includes(k)} onChange={() => toggle(k)} /> {l}
            </label>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button onClick={send} disabled={busy} className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            {runAt ? <Clock className="h-4 w-4" /> : <Send className="h-4 w-4" />} {runAt ? "排程發送" : "立即發送"}
          </button>
          {result && <span className="text-sm text-slate-500 dark:text-slate-400">{result}</span>}
        </div>
      </div>

      {scheduled.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">排程 / 已發紀錄</h2>
          <div className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
            {scheduled.map((b) => (
              <div key={b.id} className="flex items-center justify-between py-2">
                <div className="min-w-0">
                  <p className="truncate text-slate-700 dark:text-slate-200">{b.title}</p>
                  <p className="text-xs text-slate-400">{b.segment} · {(b.channels || []).join("/")} · {b.run_at ? new Date(b.run_at).toLocaleString("zh-TW") : ""} · {b.sent ? "✅ 已發送" : "⏳ 待發送"}</p>
                </div>
                {!b.sent && <button onClick={async () => { await deleteScheduledBroadcast(b.id); loadScheduled(); }} className="rounded-md border border-rose-200 px-2 py-1 text-xs text-rose-600 hover:bg-rose-50"><Trash2 className="h-3.5 w-3.5" /></button>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
