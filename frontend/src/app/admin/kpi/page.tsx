"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { useRequireAuth } from "@/components/AuthProvider";
import { getKpi, kpiExportUrl, type KpiReport } from "@/lib/api";

const tip = { contentStyle: { borderRadius: 8, fontSize: 12, border: "1px solid #cbd5e1", background: "rgba(255,255,255,0.96)" } };

export default function AdminKpiPage() {
  const { user, ready } = useRequireAuth();
  const [days, setDays] = useState(30);
  const [d, setD] = useState<KpiReport | null>(null);

  useEffect(() => { if (user) getKpi(days).then(setD).catch(() => {}); }, [user, days]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;
  if (!d) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  const cards = [
    ["總用戶", d.totals.users], ["新註冊", d.totals.new_users], ["搜尋數", d.totals.searches],
    ["DAU", d.totals.dau], ["WAU", d.totals.wau], ["MAU", d.totals.mau],
  ] as const;
  const maxFunnel = Math.max(1, ...d.funnel.map((f) => f.count));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">KPI 儀表板</h1>
        <div className="flex items-center gap-2">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900">
            <option value={7}>近 7 天</option><option value={30}>近 30 天</option><option value={90}>近 90 天</option>
          </select>
          <a href={kpiExportUrl(days)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">匯出 CSV</a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map(([l, v]) => (
          <div key={l} className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <p className="text-xs text-slate-400">{l}</p>
            <p className="mt-1 text-2xl font-bold text-slate-800 dark:text-slate-100">{v.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">每日活躍 / 新註冊 / 搜尋</h3>
          <div style={{ width: "100%", height: 240 }}><ResponsiveContainer width="100%" height="100%">
            <AreaChart data={d.daily}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
              <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} interval={Math.ceil(d.daily.length / 8)} tickFormatter={(t) => t.slice(5)} />
              <YAxis stroke="#94a3b8" fontSize={10} allowDecimals={false} />
              <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey="active" name="活躍" stroke="#2f5597" fill="#2f5597" fillOpacity={0.2} />
              <Area type="monotone" dataKey="signups" name="註冊" stroke="#10b981" fill="#10b981" fillOpacity={0.2} />
              <Area type="monotone" dataKey="searches" name="搜尋" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.15} />
            </AreaChart>
          </ResponsiveContainer></div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">新用戶活躍漏斗</h3>
          <div className="space-y-2">
            {d.funnel.map((f) => (
              <div key={f.step}>
                <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400"><span>{f.step}</span><span>{f.count}</span></div>
                <div className="mt-1 h-3 rounded-full bg-slate-100 dark:bg-slate-700">
                  <div className="h-3 rounded-full bg-brand-500" style={{ width: `${(f.count / maxFunnel) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
