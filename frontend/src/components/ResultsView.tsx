import type { CrawlResult } from "@/lib/types";
import { exportUrl } from "@/lib/api";
import StatCards from "./StatCards";
import BarChart from "./BarChart";
import ProductCards from "./ProductCards";
import ResultsTable from "./ResultsTable";
import AiSummary from "./AiSummary";

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

  return (
    <div className="space-y-5">
      <StatCards summary={summary} />

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-600">匯出:</span>
        <a href={exportUrl(runId, "csv")} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">CSV</a>
        <a href={exportUrl(runId, "xlsx")} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">Excel</a>
        <a href={exportUrl(runId, "md")} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">Markdown 報告</a>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <BarChart title="分類統計" data={summary.categories} />
        <BarChart title="來源網站 Top 10" data={summary.domains} />
      </div>

      {showAi && <AiSummary runId={runId} />}

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700">商品候選</h2>
        <ProductCards records={records} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700">完整結果</h2>
        <ResultsTable records={records} />
      </section>
    </div>
  );
}
