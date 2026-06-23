"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHistory } from "@/lib/api";
import type { HistoryRun } from "@/lib/types";

export default function HistoryPage() {
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHistory()
      .then((d) => setRuns(d.runs))
      .catch(() => setError("讀取歷史失敗,請確認後端是否啟動。"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-800">歷史紀錄</h1>
      {loading && <p className="text-sm text-slate-400">載入中…</p>}
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {!loading && !error && runs.length === 0 && (
        <p className="text-sm text-slate-400">還沒有任何搜尋紀錄,去首頁跑一次吧。</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {runs.map((run) => (
          <Link
            key={run.id}
            href={`/history/${run.id}`}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">
                {new Date(run.finished_at).toLocaleString("zh-TW")}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] ${
                  run.status === "done"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {run.status}
              </span>
            </div>
            <p className="mt-2 line-clamp-1 text-sm font-medium text-slate-700">
              {run.keywords.join("、") || "(無關鍵字)"}
            </p>
            <div className="mt-2 flex gap-4 text-xs text-slate-500">
              <span>共 {run.summary?.total ?? 0} 筆</span>
              <span>有價格 {run.summary?.with_price ?? 0} 筆</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
