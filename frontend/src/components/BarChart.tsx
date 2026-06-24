"use client";

import { BAR_COLORS } from "@/lib/format";

// 純 CSS 水平長條圖:不依賴 recharts 的容器量測,任何版面都畫得出來。
export default function BarChart({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data ?? {})
    .filter(([, v]) => typeof v === "number")
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15);
  const max = entries.reduce((m, [, v]) => Math.max(m, v), 0) || 1;

  return (
    <div className="w-full min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-400">沒有資料</p>
      ) : (
        <div className="space-y-1.5">
          {entries.map(([name, value], i) => (
            <div key={name} className="flex items-center gap-2 text-xs">
              <span className="w-24 shrink-0 truncate text-right text-slate-500 dark:text-slate-400" title={name}>{name}</span>
              <div className="relative h-5 flex-1 overflow-hidden rounded bg-slate-100 dark:bg-slate-700">
                <div
                  className="h-full rounded"
                  style={{ width: `${Math.max(4, (value / max) * 100)}%`, background: BAR_COLORS[i % BAR_COLORS.length] }}
                />
              </div>
              <span className="w-10 shrink-0 text-right font-medium text-slate-600 dark:text-slate-300">{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
