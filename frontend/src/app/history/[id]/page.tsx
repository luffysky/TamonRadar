"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { Share2 } from "lucide-react";
import { getHistoryRun, setRunShared } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";
import ResultsView from "@/components/ResultsView";
import RadarPanel from "@/components/RadarPanel";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";

export default function HistoryDetailPage({ params: paramsPromise }: { params: Promise<{ id: string }> }) {
  const params = use(paramsPromise);
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [data, setData] = useState<(CrawlResult & { keywords: string[]; shared?: boolean }) | null>(null);
  const [shared, setShared] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggleShare() {
    const next = !shared;
    try {
      await setRunShared(params.id, next);
      setShared(next);
      if (next) {
        const url = `${window.location.origin}/share/${params.id}`;
        try { await navigator.clipboard.writeText(url); toast("分享連結已複製!", "success"); }
        catch { toast(`分享開啟:${url}`, "success"); }
      } else {
        toast("已關閉分享", "info");
      }
    } catch {
      toast("設定分享失敗", "error");
    }
  }

  useEffect(() => {
    if (!user) return;
    getHistoryRun(params.id)
      .then((d) => { setData(d); setShared(!!(d as { shared?: boolean }).shared); })
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
              {data.keywords?.join("、") || "歷史紀錄"}
            </h1>
            <button onClick={toggleShare} className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition ${shared ? "border-brand-300 bg-brand-50 text-brand-600 dark:bg-brand-950/40" : "border-slate-300 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"}`}>
              <Share2 className="h-4 w-4" /> {shared ? "已分享(點此複製/關閉)" : "分享此結果"}
            </button>
          </div>
          <RadarPanel runId={params.id} />
          <ResultsView runId={params.id} result={{ records: data.records, summary: data.summary }} />
        </>
      )}
    </div>
  );
}
