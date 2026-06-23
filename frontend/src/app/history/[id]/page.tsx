"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHistoryRun } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";
import ResultsView from "@/components/ResultsView";

export default function HistoryDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<(CrawlResult & { keywords: string[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistoryRun(params.id)
      .then(setData)
      .catch(() => setError("讀取這筆紀錄失敗。"));
  }, [params.id]);

  return (
    <div className="space-y-4">
      <Link href="/history" className="text-sm text-brand-600 hover:underline">← 回歷史清單</Link>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {!data && !error && <p className="text-sm text-slate-400">載入中…</p>}
      {data && (
        <>
          <h1 className="text-xl font-bold text-slate-800">
            {data.keywords?.join("、") || "歷史紀錄"}
          </h1>
          <ResultsView runId={params.id} result={{ records: data.records, summary: data.summary }} />
        </>
      )}
    </div>
  );
}
