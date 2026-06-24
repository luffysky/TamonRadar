"use client";

import { useEffect, useState } from "react";
import { BAR_COLORS } from "@/lib/format";

export default function BarChart({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data ?? {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  const [grown, setGrown] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setGrown(true), 50);
    return () => clearTimeout(t);
  }, [data]);

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-400">沒有資料</p>
      ) : (
        <div className="space-y-2">
          {entries.map(([label, value], i) => (
            <div key={label}>
              <button
                onClick={() => setActive(active === label ? null : label)}
                className="flex w-full items-center gap-2 text-left"
              >
                <div className="w-28 shrink-0 truncate text-right text-xs text-slate-600 dark:text-slate-300" title={label}>
                  {label}
                </div>
                <div className="h-5 flex-1 overflow-hidden rounded bg-slate-100 dark:bg-slate-700">
                  <div
                    className="flex h-5 items-center justify-end rounded px-2 text-[10px] font-medium text-white transition-all duration-700 ease-out hover:brightness-110"
                    style={{
                      width: grown ? `${Math.max(8, (value / max) * 100)}%` : "0%",
                      backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
                      opacity: active && active !== label ? 0.45 : 1,
                    }}
                  >
                    {value}
                  </div>
                </div>
              </button>
              {active === label && (
                <p className="mt-1 rounded bg-slate-50 px-2 py-1 text-xs text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  {label}:{value} 筆 · 佔 {((value / total) * 100).toFixed(1)}%
                </p>
              )}
            </div>
          ))}
          <p className="pt-1 text-right text-[10px] text-slate-400">點長條看詳細</p>
        </div>
      )}
    </div>
  );
}
