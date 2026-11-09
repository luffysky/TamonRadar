"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/components/AuthProvider";
import { getAdminRun } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";
import ResultsView from "@/components/ResultsView";
import { ADMIN_BASE } from "@/lib/admin";

export default function AdminRunPage({ params: paramsPromise }: { params: Promise<{ id: string }> }) {
  const params = use(paramsPromise);
  const { user, ready } = useRequireAuth();
  const [data, setData] = useState<(CrawlResult & { keywords: string[] }) | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (user) getAdminRun(params.id).then((d) => setData({ records: d.records, summary: d.summary, keywords: d.keywords })).catch((e) => setErr(e instanceof Error ? e.message : "讀取失敗"));
  }, [user, params.id]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;
  if (err) return <p className="py-20 text-center text-sm text-rose-500">{err}</p>;
  if (!data) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  return (
    <div className="space-y-4">
      <Link href={ADMIN_BASE} className="text-sm text-brand-600 hover:underline dark:text-brand-300">← 回後台</Link>
      <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">搜尋結果:{data.keywords.join("、")}</h1>
      <ResultsView runId={params.id} result={{ records: data.records, summary: data.summary }} showAi={false} />
    </div>
  );
}
