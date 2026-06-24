"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { useRequireAuth } from "@/components/AuthProvider";
import { sendBroadcast } from "@/lib/api";

const CHANNELS: [string, string][] = [
  ["inapp", "站內通知 + 系統推播(Web Push)"],
  ["email", "Email"],
  ["tg", "Telegram(已設 chat id 者)"],
  ["discord", "Discord(已設 webhook / user id 者)"],
];

export default function AdminBroadcastsPage() {
  const { user, ready } = useRequireAuth();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const [channels, setChannels] = useState<string[]>(["inapp"]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string>("");

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;

  function toggle(c: string) {
    setChannels((cs) => (cs.includes(c) ? cs.filter((x) => x !== c) : [...cs, c]));
  }
  async function send() {
    if (!title.trim()) { setResult("請填標題"); return; }
    if (channels.length === 0) { setResult("請至少選一個管道"); return; }
    if (!confirm(`確定要發送「${title}」給全體使用者?`)) return;
    setBusy(true); setResult("發送中…");
    try {
      const r = await sendBroadcast({ title, body, url, channels });
      setResult(`✅ 已送達 ${r.recipients} 人:站內 ${r.inapp}、TG ${r.tg}、Discord ${r.discord}${r.email !== undefined ? `、Email ${r.email}` : ""}`);
      setTitle(""); setBody(""); setUrl("");
    } catch { setResult("❌ 發送失敗"); }
    finally { setBusy(false); }
  }

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900";

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">推播中心</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">一次把公告 / 活動推給全體使用者,可多管道同時發送。</p>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="標題" className={field} />
        <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="內容" rows={5} className={field} />
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="連結(選填,通知可點)" className={field} />

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
            <Send className="h-4 w-4" /> 發送給全體
          </button>
          {result && <span className="text-sm text-slate-500 dark:text-slate-400">{result}</span>}
        </div>
      </div>
    </div>
  );
}
