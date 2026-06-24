"use client";

import { useState } from "react";
import { Heart } from "lucide-react";
import type { CrawlRecord } from "@/lib/types";
import { categoryClass } from "@/lib/format";
import ProductImage from "./ProductImage";

export default function ProductCards({
  records,
  favUrls,
  onToggleFav,
  showPrice = true,
}: {
  records: CrawlRecord[];
  favUrls?: Set<string>;
  onToggleFav?: (r: CrawlRecord) => void;
  showPrice?: boolean;
}) {
  const [lightbox, setLightbox] = useState<CrawlRecord | null>(null);
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState("smart");
  const PER = 20;

  const score = (r: CrawlRecord) => ((r.price || "").trim() ? 2 : 0) + (r.image_url ? 1 : 0);
  const priceNum = (r: CrawlRecord) => {
    const n = parseInt((r.price || "").replace(/[^0-9]/g, ""), 10);
    return Number.isNaN(n) ? null : n;
  };
  const base = records.filter((r) => !r.is_listing); // 排除搜尋/列表頁
  const items = [...base].sort((a, b) => {
    if (sort === "price_asc") return (priceNum(a) ?? Infinity) - (priceNum(b) ?? Infinity);
    if (sort === "price_desc") return (priceNum(b) ?? -Infinity) - (priceNum(a) ?? -Infinity);
    if (sort === "name") return (a.title || "").localeCompare(b.title || "", "zh-Hant");
    return score(b) - score(a); // smart:有價/有圖優先
  });

  if (items.length === 0) {
    return <p className="text-sm text-slate-400">這次沒有商品頁(多為搜尋/列表頁,請看下方完整結果)。</p>;
  }

  const pageCount = Math.ceil(items.length / PER);
  const cur = Math.min(page, pageCount - 1);
  const shown = items.slice(cur * PER, (cur + 1) * PER);

  return (
    <>
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs text-slate-400">排序</span>
        <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(0); }} className="rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-900">
          <option value="smart">推薦</option>
          {showPrice && <option value="price_asc">價格:低 → 高</option>}
          {showPrice && <option value="price_desc">價格:高 → 低</option>}
          <option value="name">名稱</option>
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {shown.map((r, i) => (
          <div
            key={`${r.url}-${i}`}
            className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-soft transition hover:-translate-y-0.5 hover:shadow-lg dark:border-slate-700 dark:bg-slate-800"
          >
            {onToggleFav && (
              <button
                onClick={() => onToggleFav(r)}
                aria-label="收藏"
                className="absolute right-2 top-2 z-10 grid h-8 w-8 place-items-center rounded-full bg-white/85 text-rose-500 shadow-sm backdrop-blur hover:bg-white dark:bg-slate-900/70"
              >
                <Heart className="h-4 w-4" fill={favUrls?.has(r.url) ? "currentColor" : "none"} />
              </button>
            )}
            <button
              onClick={() => r.image_url && setLightbox(r)}
              className="aspect-square w-full overflow-hidden bg-slate-100 dark:bg-slate-700"
              aria-label="放大圖片"
            >
              <ProductImage src={r.image_url} alt={r.title} />
            </button>
            <div className="flex flex-1 flex-col p-3">
              <span className={`mb-1 w-fit rounded-full border px-2 py-0.5 text-[10px] ${categoryClass(r.category)}`}>
                {r.category || "其他"}
              </span>
              <p className="line-clamp-2 text-sm font-medium text-slate-700 dark:text-slate-200">{r.title}</p>
              <div className="mt-auto flex items-center justify-between pt-2">
                <span className="font-bold text-rose-600">{showPrice ? r.price : ""}</span>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[10px] text-brand-600 hover:underline dark:text-brand-300"
                >
                  前往 →
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>

      {pageCount > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm">
          <button onClick={() => setPage(cur - 1)} disabled={cur === 0} className="rounded-lg border border-slate-300 px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-600 dark:hover:bg-slate-700">← 上一頁</button>
          <span className="text-slate-500 dark:text-slate-400">{cur + 1} / {pageCount}(共 {items.length} 件)</span>
          <button onClick={() => setPage(cur + 1)} disabled={cur >= pageCount - 1} className="rounded-lg border border-slate-300 px-3 py-1.5 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-600 dark:hover:bg-slate-700">下一頁 →</button>
        </div>
      )}

      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 animate-fade-in"
          onClick={() => setLightbox(null)}
        >
          <div className="animate-scale-in max-h-[90vh] max-w-2xl overflow-hidden rounded-2xl bg-white dark:bg-slate-800" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={lightbox.image_url} alt={lightbox.title} className="max-h-[70vh] w-full object-contain bg-slate-100 dark:bg-slate-900" />
            <div className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{lightbox.title}</p>
                <p className="text-sm font-bold text-rose-600">{lightbox.price}</p>
              </div>
              <a href={lightbox.url} target="_blank" rel="noreferrer" className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">
                前往商品
              </a>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
