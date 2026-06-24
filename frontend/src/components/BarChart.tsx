"use client";

import { useEffect, useState } from "react";
import {
  BarChart as RBarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";
import { BAR_COLORS } from "@/lib/format";

// 動態互動長條圖(recharts)。穩定寫法:ResponsiveContainer 直接給數字 height、不額外包 height:100% 的 div。
export default function BarChart({
  title,
  data,
  onBarClick,
  activeName,
}: {
  title: string;
  data: Record<string, number>;
  onBarClick?: (name: string) => void;
  activeName?: string;
}) {
  const entries = Object.entries(data ?? {})
    .filter(([, v]) => typeof v === "number")
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([name, value]) => ({ name, value }));

  const height = Math.max(200, entries.length * 34 + 16);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  return (
    <div className="w-full min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-400">沒有資料</p>
      ) : !mounted ? (
        <div style={{ height }} />
      ) : (
        <ResponsiveContainer width="100%" height={height} debounce={50}>
          <RBarChart data={entries} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" horizontal={false} />
            <XAxis type="number" stroke="#94a3b8" fontSize={11} allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={100} stroke="#94a3b8" fontSize={11} tickLine={false} />
            <Tooltip
              cursor={{ fill: "rgba(148,163,184,0.12)" }}
              contentStyle={{ borderRadius: 8, fontSize: 12, border: "1px solid #cbd5e1", background: "rgba(255,255,255,0.96)" }}
              formatter={((v: number) => [`${v} 筆`, "數量"]) as never}
            />
            <Bar dataKey="value" radius={[0, 6, 6, 0]} animationDuration={700}
              cursor={onBarClick ? "pointer" : undefined}
              onClick={onBarClick ? ((d: { name?: string }) => d?.name && onBarClick(d.name)) as never : undefined}>
              {entries.map((e, i) => (
                <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]}
                  fillOpacity={activeName && activeName !== e.name ? 0.35 : 1} />
              ))}
            </Bar>
          </RBarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
