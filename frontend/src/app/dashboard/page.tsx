"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Heart, Radar, CalendarClock, History, Settings, Search } from "lucide-react";
import { getFavorites, getWatches, getSchedules, getHistory, getQuota, type Quota } from "@/lib/api";
import type { HistoryRun } from "@/lib/types";
import { useRequireAuth } from "@/components/AuthProvider";

export default function DashboardPage() {
  const { user, ready } = useRequireAuth();
  const [fav, setFav] = useState(0);
  const [watch, setWatch] = useState(0);
  const [sched, setSched] = useState(0);
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [quota, setQuota] = useState<Quota | null>(null);

  useEffect(() => {
    if (!user) return;
    getFavorites().then((d) => setFav(d.favorites.length)).catch(() => {});
    getWatches().then((d) => setWatch(d.watches.length)).catch(() => {});
    getSchedules().then((d) => setSched(d.schedules.length)).catch(() => {});
    getHistory().then((d) => setRuns(d.runs.slice(0, 5))).catch(() => {});
    getQuota().then(setQuota).catch(() => {});
  }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  const cards = [
    { href: "/favorites", icon: Heart, label: "收藏", value: fav, color: "text-rose-500" },
    { href: "/watches", icon: Radar, label: "監看", value: watch, color: "text-brand-500" },
    { href: "/schedules", icon: CalendarClock, label: "排程", value: sched, color: "text-amber-500" },
    { href: "/history", icon: History, label: "歷史搜尋", value: runs.length ? "查看" : 0, color: "text-emerald-500" },
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-gradient-to-br from-brand-600 to-brand-500 p-6 text-white shadow">
        <h1 className="text-2xl font-bold">我的儀表板</h1>
        <p className="mt-1 text-sm text-brand-50">{user.username || user.email} · 一眼掌握你的追蹤與動態</p>
        {quota && (
          <p className="mt-2 inline-block rounded-full bg-white/20 px-3 py-1 text-xs">
            {quota.unlimited
              ? "✨ 無限額度(特權 / 付費)"
              : `今日額度:搜尋 ${quota.search_used}/${quota.search_limit} · AI ${quota.ai_used}/${quota.ai_limit}`}
          </p>
        )}
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {cards.map((c) => (
          <Link key={c.href} href={c.href} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-700 dark:bg-slate-800">
            <c.icon className={`h-5 w-5 ${c.color}`} />
            <div className="mt-2 text-2xl font-bold text-slate-800 dark:text-slate-100">{c.value}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">{c.label}</div>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-700 dark:text-slate-200">最近搜尋</h2>
            <Link href="/" className="flex items-center gap-1 text-sm text-brand-600 hover:underline dark:text-brand-300"><Search className="h-4 w-4" />新搜尋</Link>
          </div>
          {runs.length === 0 ? (
            <p className="text-sm text-slate-400">還沒有搜尋紀錄。</p>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-700">
              {runs.map((r) => (
                <Link key={r.id} href={`/history/${r.id}`} className="flex items-center justify-between py-2 hover:opacity-80">
                  <span className="truncate text-sm text-slate-700 dark:text-slate-200">{r.keywords.join("、")}</span>
                  <span className="shrink-0 text-xs text-slate-400">{r.summary?.total ?? 0} 筆</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <Link href="/settings" className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700"><Settings className="h-4 w-4" />通知 / AI 設定</Link>
          <Link href="/watches" className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700"><Radar className="h-4 w-4" />管理監看</Link>
          <Link href="/schedules" className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700"><CalendarClock className="h-4 w-4" />管理排程</Link>
        </div>
      </div>
    </div>
  );
}
