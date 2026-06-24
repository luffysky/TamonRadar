"use client";

import { useEffect, useState } from "react";
import { TrendingDown, Award, Layers, AlertTriangle, BarChart3 } from "lucide-react";
import { getInsights, type DeepInsights } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";

export default function InsightsPanel({ runId, records }: { runId?: string; records?: CrawlResult["records"] }) {
  const [data, setData] = useState<DeepInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let on = true;
    setLoading(true);
    getInsights(runId, records as unknown[])
      .then((d) => on && setData(d))
      .catch(() => on && setData(null))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [runId, records]);

  if (loading) return <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-800">深度情報分析中…</div>;
  if (!data || data.total === 0) return null;
  const s = data.price_stats as DeepInsights["price_stats"] & { count?: number };
  const hasPrice = s && (s as { count?: number }).count;

  return (
    <div className="space-y-4 rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50/60 to-white p-5 shadow-sm dark:border-brand-900 dark:from-brand-950/30 dark:to-slate-800">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-100"><BarChart3 className="h-5 w-5 text-brand-600" /> 深度情報分析</h3>
        <button onClick={() => setOpen(!open)} className="text-xs text-slate-400 hover:text-slate-600">{open ? "收起" : "展開"}</button>
      </div>

      {open && (
        <>
          {hasPrice ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[["行情中位數", `NT$${(s.median ?? 0).toLocaleString()}`], ["最低", `NT$${(s.min ?? 0).toLocaleString()}`], ["最高", `NT$${(s.max ?? 0).toLocaleString()}`], ["常見區間", `${(s.p25 ?? 0).toLocaleString()}–${(s.p75 ?? 0).toLocaleString()}`]].map(([l, v]) => (
                <div key={l} className="rounded-xl bg-white p-3 text-center shadow-sm dark:bg-slate-900">
                  <p className="text-[11px] text-slate-400">{l}</p>
                  <p className="mt-0.5 text-sm font-bold text-slate-700 dark:text-slate-200">{v}</p>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-slate-400">此次結果沒有足夠的價格可做行情分析。</p>}

          <div className="grid gap-4 md:grid-cols-2">
            {data.good_deals.length > 0 && (
              <div>
                <p className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold text-emerald-600"><TrendingDown className="h-4 w-4" /> 最划算(低於行情)</p>
                <div className="space-y-1.5">
                  {data.good_deals.slice(0, 5).map((d, i) => (
                    <a key={i} href={d.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-2 rounded-lg bg-white p-2 text-xs shadow-sm hover:bg-emerald-50 dark:bg-slate-900 dark:hover:bg-slate-700">
                      <span className="truncate text-slate-700 dark:text-slate-200">{d.title}</span>
                      <span className="shrink-0 font-bold text-emerald-600">NT${d.price_twd.toLocaleString()} <span className="rounded bg-emerald-100 px-1 text-[10px] text-emerald-700">↓{d.discount_pct}%</span></span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {data.clusters.length > 0 && (
              <div>
                <p className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold text-brand-600"><Layers className="h-4 w-4" /> 同商品跨站比價</p>
                <div className="space-y-1.5">
                  {data.clusters.slice(0, 5).map((c, i) => (
                    <div key={i} className="rounded-lg bg-white p-2 text-xs shadow-sm dark:bg-slate-900">
                      <p className="truncate text-slate-700 dark:text-slate-200">{c.title}</p>
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        {c.count} 個賣場{c.min_twd ? ` · 最低 ` : ""}
                        {c.min_twd ? <a href={c.cheapest_url} target="_blank" rel="noreferrer" className="font-bold text-brand-600 hover:underline">NT${c.min_twd.toLocaleString()} @ {c.cheapest_domain}</a> : ""}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            {Object.entries(data.status_dist).map(([k, v]) => (
              <span key={k} className="rounded-full bg-white px-2.5 py-1 text-slate-600 shadow-sm dark:bg-slate-900 dark:text-slate-300">{k} {v}</span>
            ))}
            {Object.entries(data.trust_dist).map(([k, v]) => (
              <span key={k} className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-500 dark:bg-slate-700 dark:text-slate-400">{k} {v}</span>
            ))}
          </div>

          {data.best_value && (
            <div className="flex items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
              <Award className="h-5 w-5 shrink-0 text-amber-500" />
              <span className="text-slate-700 dark:text-slate-200">最佳CP值推薦:<a href={data.best_value.url} target="_blank" rel="noreferrer" className="font-semibold text-amber-700 hover:underline dark:text-amber-300">{data.best_value.title}</a>（NT${data.best_value.price_twd.toLocaleString()}，划算分 {data.best_value.deal_score}）</span>
            </div>
          )}

          {data.outliers.length > 0 && (
            <div className="rounded-xl bg-rose-50 p-3 text-xs dark:bg-rose-950/30">
              <p className="mb-1 flex items-center gap-1.5 font-semibold text-rose-600"><AlertTriangle className="h-4 w-4" /> 價格異常提醒</p>
              {data.outliers.slice(0, 4).map((o, i) => (
                <p key={i} className="truncate text-slate-600 dark:text-slate-300">{o.title} — NT${o.price_twd.toLocaleString()}（{o.reason}）</p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
