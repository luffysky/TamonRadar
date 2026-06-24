"use client";

import { useEffect, useState } from "react";
import { Radar } from "lucide-react";
import { getHistoryDiff, type RadarDiff, type RadarItem } from "@/lib/api";
import ProductImage from "./ProductImage";

function ItemRow({ item, kind }: { item: RadarItem; kind: "new" | "drop" | "restock" }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noreferrer"
      className="flex h-full items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2 hover:border-brand-300 hover:shadow-sm"
    >
      <div className="h-11 w-11 shrink-0 overflow-hidden rounded bg-slate-100 dark:bg-slate-700">
        <ProductImage src={item.image_url} alt={item.title} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{item.title}</p>
        <p className="truncate text-xs text-slate-400">{item.domain}</p>
      </div>
      <div className="shrink-0 text-right">
        {kind === "drop" ? (
          <>
            <div className="text-xs text-slate-400 line-through">{item.old_price}</div>
            <div className="text-sm font-bold text-rose-600 whitespace-nowrap">
              {item.price} <span className="text-xs">↓{item.drop_pct}%</span>
            </div>
          </>
        ) : (
          <div className="text-sm font-bold text-emerald-600 whitespace-nowrap">{item.price || "—"}</div>
        )}
      </div>
    </a>
  );
}

function Section({ title, color, items, kind }: {
  title: string; color: string; items: RadarItem[]; kind: "new" | "drop" | "restock";
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className={`mb-2 text-sm font-semibold ${color}`}>{title}（{items.length}）</h4>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {items.slice(0, 8).map((it, i) => (
          <ItemRow key={`${it.url}-${i}`} item={it} kind={kind} />
        ))}
      </div>
    </div>
  );
}

export default function RadarPanel({ runId }: { runId: string }) {
  const [data, setData] = useState<RadarDiff | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHistoryDiff(runId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 text-sm text-slate-400 shadow-sm">
        價格雷達分析中…
      </div>
    );
  }

  if (!data?.has_previous || !data.diff) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 text-sm text-slate-400 shadow-sm">
        價格雷達：這是第一筆紀錄，還沒有可比較的上一次。再搜尋一次同樣的關鍵字就能看到變化。
      </div>
    );
  }

  const { counts } = data.diff;
  const noChange = counts.new + counts.price_drops + counts.restock === 0;

  return (
    <div className="space-y-4 rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 to-white p-5 shadow-sm dark:border-brand-700 dark:from-slate-800 dark:to-slate-800">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="flex items-center gap-1.5 text-base font-bold text-brand-700"><Radar className="h-5 w-5" /> 價格雷達</h3>
        <span className="text-xs text-slate-400">
          對比上一次（{data.previous_at ? new Date(data.previous_at).toLocaleString("zh-TW") : ""}）
        </span>
        <div className="ml-auto flex gap-2 text-xs">
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">新品 {counts.new}</span>
          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-rose-700">降價 {counts.price_drops}</span>
          <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">補貨 {counts.restock}</span>
        </div>
      </div>

      {noChange ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">跟上一次相比沒有明顯變化。</p>
      ) : (
        <div className="space-y-4">
          <Section title="降價" color="text-rose-600" items={data.diff.price_drops} kind="drop" />
          <Section title="新出現" color="text-emerald-600" items={data.diff.new_items} kind="new" />
          <Section title="補貨 / 新上架價" color="text-sky-600" items={data.diff.restock} kind="restock" />
        </div>
      )}
    </div>
  );
}
