"use client";

import { Search, ExternalLink } from "lucide-react";
import type { CrawlRecord } from "@/lib/types";

export default function ListingCards({ records }: { records: CrawlRecord[] }) {
  const items = records.filter((r) => r.is_listing).slice(0, 16);
  if (items.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((r, i) => (
        <a
          key={`${r.url}-${i}`}
          href={r.url}
          target="_blank"
          rel="noreferrer"
          className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-700 dark:bg-slate-800"
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-600 dark:bg-amber-950 dark:text-amber-300">
            <Search className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{r.title}</p>
            <p className="truncate text-xs text-slate-400">{r.domain}</p>
          </div>
          <ExternalLink className="h-4 w-4 shrink-0 text-slate-300 group-hover:text-brand-500" />
        </a>
      ))}
    </div>
  );
}
