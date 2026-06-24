"use client";

import { useEffect, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getAdminCharts, type AdminCharts } from "@/lib/api";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
      {children}
    </div>
  );
}

const tip = { contentStyle: { borderRadius: 8, fontSize: 12, border: "1px solid #cbd5e1", background: "rgba(255,255,255,0.96)" } };

export default function DashboardCharts() {
  const [d, setD] = useState<AdminCharts | null>(null);
  useEffect(() => { getAdminCharts().then(setD).catch(() => {}); }, []);
  if (!d) return null;

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card title="📈 註冊趨勢(近 30 天)">
        <div style={{ width: "100%", height: 200 }}><ResponsiveContainer width="100%" height="100%">
          <AreaChart data={d.signups}>
            <defs>
              <linearGradient id="g-su" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#2f5597" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#2f5597" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
            <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} interval={4} />
            <YAxis stroke="#94a3b8" fontSize={10} allowDecimals={false} />
            <Tooltip {...tip} />
            <Area type="monotone" dataKey="count" name="新註冊" stroke="#2f5597" fill="url(#g-su)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer></div>
      </Card>

      <Card title="🤖 AI / 搜尋用量(近 30 天)">
        <div style={{ width: "100%", height: 200 }}><ResponsiveContainer width="100%" height="100%">
          <BarChart data={d.ai_usage}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
            <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} interval={4} />
            <YAxis stroke="#94a3b8" fontSize={10} allowDecimals={false} />
            <Tooltip {...tip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="ai" name="AI" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
            <Bar dataKey="search" name="搜尋" fill="#22c55e" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer></div>
      </Card>

      <Card title="📊 內容成長(搜尋次數 / 文章)">
        <div style={{ width: "100%", height: 200 }}><ResponsiveContainer width="100%" height="100%">
          <LineChart data={d.content}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
            <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} interval={4} />
            <YAxis stroke="#94a3b8" fontSize={10} allowDecimals={false} />
            <Tooltip {...tip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="runs" name="搜尋" stroke="#2f5597" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="posts" name="文章" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer></div>
      </Card>
    </div>
  );
}
