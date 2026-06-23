"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHistoryRun } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";
import ResultsView from "@/components/ResultsView";
import RadarPanel from "@/components/RadarPanel";
import { useRequireAuth } from "@/components/AuthProvider";

export default function HistoryDetailPage({ params }: { params: { id: string } }) {
  const { user, ready } = useRequireAuth();
  const [data, setData] = useState<(CrawlResult & { keywords: string[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    getHistoryRun(params.id)
      .then(setData)
      .catch((e) => {
        if (e instanceof Error && e.message === "UNAUTHORIZED") return;
        setError("讀取這筆紀錄失敗。");
      });
  }, [params.id, user]);

  if (!ready || !user) {
    return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  }

  return (
    <div className="space-y-4">
      <Link href="/history" className="text-sm text-brand-600 hover:underline">← 回歷史清單</Link>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {!data && !error && <p className="text-sm text-slate-400">載入中…</p>}
      {data && (
        <>
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {data.keywords?.join("、") || "歷史紀錄"}
          </h1>
          <RadarPanel runId={params.id} />
          <ResultsView runId={params.id} result={{ records: data.records, summary: data.summary }} />
        </>
      )}
    </div>
  );
}
