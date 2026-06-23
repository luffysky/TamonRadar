"use client";

import { useEffect, useState } from "react";
import {
  getSchedules, createSchedule, updateSchedule, deleteSchedule, runSchedule,
  type Schedule, type ScheduleInput,
} from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";

const PROVIDERS = [
  { value: "brave", label: "Brave API" },
  { value: "serpapi", label: "SerpAPI" },
  { value: "selenium", label: "Selenium" },
];

export default function SchedulesPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [keywords, setKeywords] = useState("多聞 公仔\n多聞 壓克力");
  const [provider, setProvider] = useState("brave");
  const [interval, setInterval] = useState(24);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const d = await getSchedules();
      setSchedules(d.schedules);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (user) reload();
  }, [user]);

  if (!ready || !user) {
    return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  }

  async function add() {
    const list = keywords.split("\n").map((k) => k.trim()).filter(Boolean);
    if (list.length === 0) return;
    setBusy(true);
    try {
      const data: ScheduleInput = {
        keywords: list, provider, pages: 2, max_detail: 0,
        scrape_details: false, interval_hours: interval, enabled: true,
      };
      await createSchedule(data);
      await reload();
      toast("已新增排程", "success");
    } catch {
      toast("新增失敗", "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(sc: Schedule) {
    await updateSchedule(sc.id, { ...sc, enabled: !sc.enabled });
    reload();
    toast(sc.enabled ? "已停用" : "已啟用", "info");
  }

  async function remove(id: number) {
    await deleteSchedule(id);
    reload();
    toast("已刪除排程", "info");
  }

  async function runNow(id: number) {
    await runSchedule(id);
    toast("已在背景開始執行,完成後依通知設定推播", "success");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">排程自動搜尋</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          設定後系統會定時自動爬,跟上次比較有變化就推播(記得先到「通知設定」設好管道)。
        </p>
      </div>

      <div className="grid gap-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-sm sm:grid-cols-[1fr_auto]">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">關鍵字(一行一個)</label>
          <textarea
            value={keywords} onChange={(e) => setKeywords(e.target.value)} rows={3}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 p-2 text-sm focus:border-brand-500 focus:outline-none"
          />
        </div>
        <div className="flex flex-col gap-2 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-slate-600 dark:text-slate-300">搜尋來源</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5">
              {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-slate-600 dark:text-slate-300">每隔幾小時</span>
            <input type="number" min={1} max={168} value={interval} onChange={(e) => setInterval(Number(e.target.value))} className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5" />
          </label>
          <button onClick={add} disabled={busy} className="mt-auto rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            新增排程
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {schedules.length === 0 && <p className="text-sm text-slate-400">還沒有排程。</p>}
        {schedules.map((sc) => (
          <div key={sc.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{sc.keywords.join("、")}</p>
              <p className="text-xs text-slate-400">
                {PROVIDERS.find((p) => p.value === sc.provider)?.label} · 每 {sc.interval_hours} 小時
                {sc.last_run ? ` · 上次 ${new Date(sc.last_run).toLocaleString("zh-TW")}` : " · 尚未執行"}
              </p>
            </div>
            <span className={`rounded-full px-2 py-0.5 text-xs ${sc.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"}`}>
              {sc.enabled ? "啟用中" : "已停用"}
            </span>
            <button onClick={() => runNow(sc.id)} className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-xs hover:bg-slate-50 dark:bg-slate-900">立即執行</button>
            <button onClick={() => toggle(sc)} className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-xs hover:bg-slate-50 dark:bg-slate-900">{sc.enabled ? "停用" : "啟用"}</button>
            <button onClick={() => remove(sc.id)} className="rounded-md border border-rose-200 px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50">刪除</button>
          </div>
        ))}
      </div>
    </div>
  );
}
