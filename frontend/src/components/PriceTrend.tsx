"use client";

import { useEffect, useState } from "react";
import { getPriceHistory } from "@/lib/api";

export default function PriceTrend({ url }: { url: string }) {
  const [pts, setPts] = useState<{ date: string; price_twd: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPriceHistory(url)
      .then((d) => setPts(d.history))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [url]);

  if (loading) return <span className="text-xs text-slate-400">走勢載入中…</span>;
  if (pts.length < 2) return <span className="text-xs text-slate-400">走勢資料不足(需多次搜尋累積)</span>;

  const w = 200, h = 48, pad = 4;
  const vals = pts.map((p) => p.price_twd);
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const coords = pts.map((p, i) => {
    const x = pad + (i / (pts.length - 1)) * (w - pad * 2);
    const y = h - pad - ((p.price_twd - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const latest = vals[vals.length - 1];
  const first = vals[0];
  const down = latest < first;

  return (
    <div className="flex items-center gap-2">
      <svg width={w} height={h} className="overflow-visible">
        <polyline
          points={coords.join(" ")}
          fill="none"
          stroke={down ? "#10b981" : "#ef4444"}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      <div className="text-xs">
        <div className={down ? "font-semibold text-emerald-600" : "font-semibold text-rose-600"}>NT${latest.toLocaleString()}</div>
        <div className="text-slate-400">低 {min.toLocaleString()} / 高 {max.toLocaleString()}</div>
      </div>
    </div>
  );
}
