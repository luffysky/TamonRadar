"use client";

import { useState } from "react";
import type { CrawlRecord } from "@/lib/types";
import { categoryClass } from "@/lib/format";
import ProductImage from "./ProductImage";

export default function ProductCards({ records }: { records: CrawlRecord[] }) {
  const [lightbox, setLightbox] = useState<CrawlRecord | null>(null);

  const score = (r: CrawlRecord) => ((r.price || "").trim() ? 2 : 0) + (r.image_url ? 1 : 0);
  const items = [...records]
    .filter((r) => !r.is_listing) // 排除搜尋/列表頁,只放真正的商品/內容頁
    .sort((a, b) => score(b) - score(a))
    .slice(0, 24);

  if (items.length === 0) {
    return <p className="text-sm text-slate-400">這次沒有商品頁(多為搜尋/列表頁,請看下方完整結果)。</p>;
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((r, i) => (
          <div
            key={`${r.url}-${i}`}
            className="group flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-soft transition hover:-translate-y-0.5 hover:shadow-lg dark:border-slate-700 dark:bg-slate-800"
          >
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
                <span className="font-bold text-rose-600">{r.price}</span>
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
