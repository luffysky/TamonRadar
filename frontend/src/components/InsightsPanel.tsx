"use client";

import { useEffect, useState } from "react";
import { TrendingDown, Award, Layers, AlertTriangle, BarChart3, Sparkles, ArrowDownUp } from "lucide-react";
import { getInsights, getRunCompare, getAiInsight, type DeepInsights, type RunCompare } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";
import Markdown from "./Markdown";

export default function InsightsPanel({ runId, records, vertical = "" }: { runId?: string; records?: CrawlResult["records"]; vertical?: string }) {
  const [data, setData] = useState<DeepInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(true);
  const [cmp, setCmp] = useState<RunCompare | null>(null);
  const [aiText, setAiText] = useState("");
  const [aiEntities, setAiEntities] = useState<{ title: string; url: string; price_twd: number | null; domain: string; note: string }[]>([]);
  const [aiBusy, setAiBusy] = useState(false);

  useEffect(() => {
    let on = true;
    setLoading(true);
    getInsights(runId, records as unknown[], vertical)
      .then((d) => on && setData(d))
      .catch(() => on && setData(null))
      .finally(() => on && setLoading(false));
    if (runId) getRunCompare(runId).then((c) => on && setCmp(c)).catch(() => {});
    return () => { on = false; };
  }, [runId, records, vertical]);

  async function runAiInsight() {
    if (!runId) return;
    setAiBusy(true); setAiText("");
    try { const r = await getAiInsight(runId, vertical); setAiText(r.insight); setAiEntities(r.entities || []); }
    catch (e) { setAiText(e instanceof Error ? e.message : "AI 洞察失敗"); }
    finally { setAiBusy(false); }
  }

  if (loading) return <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-800">深度情報分析中…</div>;
  if (!data || data.total === 0) return null;
  const s = data.price_stats as DeepInsights["price_stats"] & { count?: number };
  const hasPrice = s && (s as { count?: number }).count;

  return (
    <div className="space-y-4 rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50/60 to-white p-5 shadow-sm dark:border-brand-900 dark:from-brand-950/30 dark:to-slate-800">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-100"><BarChart3 className="h-5 w-5 text-brand-600" /> 深度情報分析</h3>
        <div className="flex items-center gap-2">
          {runId && <button onClick={runAiInsight} disabled={aiBusy} className="flex items-center gap-1 rounded-lg bg-violet-600 px-3 py-1 text-xs text-white hover:bg-violet-700 disabled:opacity-50"><Sparkles className="h-3.5 w-3.5" /> {aiBusy ? "分析中…" : "AI 洞察"}</button>}
          <button onClick={() => setOpen(!open)} className="text-xs text-slate-400 hover:text-slate-600">{open ? "收起" : "展開"}</button>
        </div>
      </div>

      {aiText && (
        <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4 text-sm dark:border-violet-900 dark:bg-violet-950/30">
          <Markdown>{aiText}</Markdown>
          {aiEntities.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2 border-t border-violet-200 pt-3 dark:border-violet-900">
              {aiEntities.map((e, i) => (
                <a key={i} href={e.url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-xs shadow-sm hover:bg-violet-100 dark:bg-slate-900 dark:hover:bg-slate-700">
                  <span className="rounded bg-violet-100 px-1 text-[10px] text-violet-700 dark:bg-violet-900 dark:text-violet-300">{e.note}</span>
                  <span className="max-w-[160px] truncate text-slate-700 dark:text-slate-200">{e.title}</span>
                  {e.price_twd ? <span className="font-semibold text-brand-600">NT${e.price_twd.toLocaleString()}</span> : null}
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {open && cmp && cmp.has_previous && ((cmp.cheaper?.length || 0) > 0 || (cmp.pricier?.length || 0) > 0) && (
        <div className="rounded-xl bg-white p-3 text-sm shadow-sm dark:bg-slate-900">
          <p className="mb-1.5 flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-200"><ArrowDownUp className="h-4 w-4" /> 跟上次比較{cmp.prev_date ? `(${new Date(cmp.prev_date).toLocaleDateString("zh-TW")})` : ""}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <p className="text-xs font-medium text-emerald-600">↓ 變便宜 {cmp.cheaper?.length || 0}</p>
              {(cmp.cheaper || []).slice(0, 4).map((c, i) => (
                <p key={i} className="truncate text-xs text-slate-500 dark:text-slate-400">{c.title} <span className="text-emerald-600">NT${c.was}→{c.now}</span></p>
              ))}
            </div>
            <div>
              <p className="text-xs font-medium text-rose-500">↑ 變貴 {cmp.pricier?.length || 0}</p>
              {(cmp.pricier || []).slice(0, 4).map((c, i) => (
                <p key={i} className="truncate text-xs text-slate-500 dark:text-slate-400">{c.title} <span className="text-rose-500">NT${c.was}→{c.now}</span></p>
              ))}
            </div>
          </div>
          {(cmp.new_items?.length || 0) > 0 && <p className="mt-1.5 text-xs text-slate-400">🆕 新出現:{cmp.new_items!.slice(0, 5).join("、")}</p>}
        </div>
      )}

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

          {data.facets && data.facets.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.facets.map((f, i) => (
                <div key={i} className="rounded-xl bg-white p-3 shadow-sm dark:bg-slate-900">
                  <p className="mb-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300">{f.label}</p>
                  {f.type === "range" ? (
                    <p className="text-sm text-slate-700 dark:text-slate-200">
                      {f.min}{f.unit} ~ {f.max}{f.unit} <span className="text-xs text-slate-400">(中位 {f.median}{f.unit}・{f.count} 筆)</span>
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {(f.items || []).length === 0 ? <span className="text-xs text-slate-400">—</span> : (f.items || []).map((it) => (
                        <span key={it.name} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">{it.name} {it.count}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
