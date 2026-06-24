"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getSharedRun } from "@/lib/api";
import type { CrawlResult } from "@/lib/types";
import StatCards from "@/components/StatCards";
import ProductCards from "@/components/ProductCards";
import ResultsTable from "@/components/ResultsTable";

export default function ShareView({ id }: { id: string }) {
  const [data, setData] = useState<(CrawlResult & { keywords: string[] }) | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getSharedRun(id)
      .then((d) => setData({ records: d.records, summary: d.summary, keywords: d.keywords }))
      .catch((e) => setErr(e instanceof Error ? e.message : "讀取失敗"));
  }, [id]);

  if (err) return (
    <div className="py-20 text-center">
      <p className="text-sm text-rose-500">{err}</p>
      <Link href="/" className="mt-3 inline-block text-sm text-brand-600 hover:underline">回首頁搜尋</Link>
    </div>
  );
  if (!data) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-gradient-to-br from-brand-600 to-brand-500 p-5 text-white">
        <p className="text-xs text-brand-50">分享的搜尋結果</p>
        <h1 className="text-xl font-bold">{data.keywords.join("、") || "搜尋結果"}</h1>
        <Link href="/" className="mt-2 inline-block rounded-lg bg-white/20 px-3 py-1 text-sm hover:bg-white/30">在 TamonRadar 自己搜尋 →</Link>
      </div>
      <StatCards summary={data.summary} />
      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700 dark:text-slate-200">商品候選</h2>
        <ProductCards records={data.records} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-700 dark:text-slate-200">完整結果</h2>
        <ResultsTable records={data.records} />
      </section>
    </div>
  );
}
