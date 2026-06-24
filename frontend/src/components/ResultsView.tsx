"use client";

import { useState } from "react";
import type { CrawlResult } from "@/lib/types";
import { exportUrl, aiClean } from "@/lib/api";
import StatCards from "./StatCards";
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
}: {
  runId: string;
  result: CrawlResult;
  showAi?: boolean;
}) {
  const { records, summary } = result;
  const [hiddenUrls, setHiddenUrls] = useState<Set<string>>(new Set());
  const [cleaning, setCleaning] = useState(false);
  const [cleanMsg, setCleanMsg] = useState<string | null>(null);

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
          <button onClick={clean} disabled={cleaning} className="rounded-lg border border-violet-300 bg-white dark:bg-slate-800 px-3 py-1.5 text-sm text-violet-600 hover:bg-violet-50 disabled:opacity-50">
            {cleaning ? "整理中…" : "🧹 AI 濾雜訊"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <BarChart title="分類統計" data={summary.categories} />
        <BarChart title="來源網站 Top 10" data={summary.domains} />
      </div>

      {showAi && (
        <div className="grid gap-4 lg:grid-cols-2">
          <AiSummary runId={runId} />
          <AiChat runId={runId} />
        </div>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700 dark:text-slate-200">商品候選</h2>
        <ProductCards records={records.filter((r) => !hiddenUrls.has(r.url))} />
      </section>

      {records.some((r) => r.is_listing) && (
        <section>
          <h2 className="mb-1 text-lg font-semibold text-slate-700 dark:text-slate-200">各網站搜尋結果</h2>
          <p className="mb-3 text-xs text-slate-400">點進去是該網站的搜尋/列表頁,可看到更多同類商品。</p>
          <ListingCards records={records.filter((r) => !hiddenUrls.has(r.url))} />
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700 dark:text-slate-200">完整結果</h2>
        <ResultsTable records={records} hiddenUrls={hiddenUrls} />
      </section>
    </div>
  );
}
