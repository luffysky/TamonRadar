"use client";

import { useEffect, useState } from "react";
import type { CrawlResult, CrawlRecord } from "@/lib/types";
import { exportUrl, aiClean, aiCompare, getFavorites, addFavorite, removeFavorite } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { getVertical } from "@/lib/verticals";
import { Sparkles, GitCompare } from "lucide-react";
import Markdown from "./Markdown";
import StatCards from "./StatCards";
import InsightsPanel from "./InsightsPanel";
import BarChart from "./BarChart";
import ProductCards from "./ProductCards";
import ListingCards from "./ListingCards";
import ResultsTable from "./ResultsTable";
import AiSummary from "./AiSummary";
import AiChat from "./AiChat";

export default function ResultsView({
  runId,
  result,
  showAi = true,
  vertical = "merch",
}: {
  runId: string;
  result: CrawlResult;
  showAi?: boolean;
  vertical?: string;
}) {
  const { records, summary } = result;
  const v = getVertical(vertical);

  // summary 若沒帶分類/來源,就直接從 records 重算(保證圖表有資料)
  function countBy(field: "category" | "domain", topN = 0): Record<string, number> {
    const m: Record<string, number> = {};
    for (const r of records) {
      const k = (r[field] || (field === "category" ? "未分類" : "")).toString().trim();
      if (k) m[k] = (m[k] || 0) + 1;
    }
    if (!topN) return m;
    return Object.fromEntries(Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, topN));
  }
  const catData = summary?.categories && Object.keys(summary.categories).length ? summary.categories : countBy("category");
  const domData = summary?.domains && Object.keys(summary.domains).length ? summary.domains : countBy("domain", 10);
  const candTitle = v.kind === "product" ? "商品候選" : `${v.label}精選`;
  const showPrice = v.kind === "product";
  const { user } = useAuth();
  const [hiddenUrls, setHiddenUrls] = useState<Set<string>>(new Set());
  const [cleaning, setCleaning] = useState(false);
  const [cleanMsg, setCleanMsg] = useState<string | null>(null);
  const [favUrls, setFavUrls] = useState<Set<string>>(new Set());
  const [favIds, setFavIds] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [compareMd, setCompareMd] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);

  function toggleSelect(url: string) {
    setSelected((s) => { const n = new Set(s); n.has(url) ? n.delete(url) : n.add(url); return n; });
  }
  async function doCompare() {
    setComparing(true);
    setCompareMd(null);
    try {
      const r = await aiCompare(runId, [...selected]);
      setCompareMd(r.answer);
    } catch (e) {
      setCompareMd(e instanceof Error ? e.message : "比較失敗");
    } finally {
      setComparing(false);
    }
  }

  useEffect(() => {
    if (!user) return;
    getFavorites()
      .then((d) => {
        setFavUrls(new Set(d.urls));
        const m: Record<string, number> = {};
        d.favorites.forEach((f) => (m[f.url] = f.id));
        setFavIds(m);
      })
      .catch(() => {});
  }, [user]);

  async function toggleFav(r: CrawlRecord) {
    try {
      if (favUrls.has(r.url)) {
        const id = favIds[r.url];
        if (id) await removeFavorite(id);
        setFavUrls((s) => { const n = new Set(s); n.delete(r.url); return n; });
      } else {
        const f = await addFavorite({ url: r.url, title: r.title, image_url: r.image_url, domain: r.domain, price: r.price });
        setFavUrls((s) => new Set(s).add(r.url));
        setFavIds((m) => ({ ...m, [r.url]: f.id }));
      }
    } catch {
      /* ignore */
    }
  }

  async function clean() {
    setCleaning(true);
    setCleanMsg(null);
    try {
      const res = await aiClean(runId);
      if (!res.available) {
        setCleanMsg("需要設定 ANTHROPIC_API_KEY 才能用 AI 濾雜訊。");
      } else {
        setHiddenUrls(new Set(res.noise_urls));
        setCleanMsg(`已隱藏 ${res.noise_urls.length} 筆 AI 判定的雜訊。`);
      }
    } catch {
      setCleanMsg("AI 整理失敗,請稍後再試。");
    } finally {
      setCleaning(false);
    }
  }

  return (
    <div className="space-y-5">
      <StatCards summary={summary} />

      <InsightsPanel runId={runId} vertical={vertical} />


      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-600 dark:text-slate-300">匯出:</span>
        <a href={exportUrl(runId, "csv")} className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-50 dark:bg-slate-900">CSV</a>
        <a href={exportUrl(runId, "xlsx")} className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-50 dark:bg-slate-900">Excel</a>
        <a href={exportUrl(runId, "md")} className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-50 dark:bg-slate-900">Markdown 報告</a>
        <div className="ml-auto flex items-center gap-2">
          {cleanMsg && <span className="text-xs text-slate-400">{cleanMsg}</span>}
          {hiddenUrls.size > 0 && (
            <button onClick={() => { setHiddenUrls(new Set()); setCleanMsg(null); }} className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-50 dark:bg-slate-900">
              還原全部
            </button>
          )}
          <button onClick={clean} disabled={cleaning} className="flex items-center gap-1 rounded-lg border border-violet-300 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-violet-600 hover:bg-violet-50 disabled:opacity-50">
            <Sparkles className="h-4 w-4" /> {cleaning ? "整理中…" : "AI 濾雜訊"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <BarChart title="分類統計" data={catData} />
        <BarChart title="來源網站 Top 10" data={domData} />
      </div>

      {showAi && (
        <div className="grid gap-4 lg:grid-cols-2">
          <AiSummary runId={runId} />
          <AiChat runId={runId} />
        </div>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700 dark:text-slate-200">{candTitle}</h2>
        <ProductCards records={records.filter((r) => !hiddenUrls.has(r.url))} favUrls={favUrls} onToggleFav={user ? toggleFav : undefined} showPrice={showPrice} />
      </section>

      {records.some((r) => r.is_listing) && (
        <section>
          <h2 className="mb-1 text-lg font-semibold text-slate-700 dark:text-slate-200">各網站搜尋結果</h2>
          <p className="mb-3 text-xs text-slate-400">點進去是該網站的搜尋/列表頁,可看到更多同類商品。</p>
          <ListingCards records={records.filter((r) => !hiddenUrls.has(r.url))} />
        </section>
      )}

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-700 dark:text-slate-200">完整結果</h2>
          {selected.size > 0 && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">已選 {selected.size}</span>
              <button onClick={doCompare} disabled={selected.size < 2 || comparing} className="flex items-center gap-1 rounded-lg bg-violet-600 px-3 py-1.5 text-white hover:bg-violet-700 disabled:opacity-50">
                <GitCompare className="h-4 w-4" /> {comparing ? "比較中…" : "AI 比較選取"}
              </button>
              <button onClick={() => setSelected(new Set())} className="rounded-lg border border-slate-300 px-3 py-1.5 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">清除</button>
            </div>
          )}
        </div>
        {compareMd && (
          <div className="mb-3 rounded-xl border border-violet-200 bg-violet-50/50 p-4 dark:border-violet-900 dark:bg-violet-950/30">
            <Markdown>{compareMd}</Markdown>
          </div>
        )}
        <ResultsTable records={records} hiddenUrls={hiddenUrls} selectedUrls={selected} onToggleSelect={user ? toggleSelect : undefined} showPrice={showPrice} />
      </section>
    </div>
  );
}
