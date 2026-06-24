"use client";

import { useMemo, useState } from "react";
import type { CrawlRecord } from "@/lib/types";
import { categoryClass } from "@/lib/format";

type SortKey = "title" | "category" | "domain" | "price";

function priceValue(p: string): number {
  const n = parseInt((p || "").replace(/[^0-9]/g, ""), 10);
  return Number.isNaN(n) ? -1 : n;
}

export default function ResultsTable({
  records,
  hiddenUrls,
  selectedUrls,
  onToggleSelect,
}: {
  records: CrawlRecord[];
  hiddenUrls?: Set<string>;
  selectedUrls?: Set<string>;
  onToggleSelect?: (url: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部");
  const [character, setCharacter] = useState("全部");
  const [onlyPrice, setOnlyPrice] = useState(false);
  const [onlyProducts, setOnlyProducts] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("category");
  const [sortAsc, setSortAsc] = useState(true);

  const categories = useMemo(() => {
    const set = new Set(records.map((r) => r.category).filter(Boolean));
    return ["全部", ...Array.from(set)];
  }, [records]);

  const characters = useMemo(() => {
    const set = new Set(records.map((r) => String(r.character ?? "")).filter(Boolean));
    return ["全部", ...Array.from(set)];
  }, [records]);

  const filtered = useMemo(() => {
    let rows = records;
    if (hiddenUrls && hiddenUrls.size) rows = rows.filter((r) => !hiddenUrls.has(r.url));
    if (category !== "全部") rows = rows.filter((r) => r.category === category);
    if (character !== "全部") rows = rows.filter((r) => String(r.character ?? "") === character);
    if (onlyPrice) rows = rows.filter((r) => (r.price || "").trim() !== "");
    if (onlyProducts) rows = rows.filter((r) => !r.is_listing);
    if (query.trim()) {
      const q = query.toLowerCase();
      rows = rows.filter(
        (r) =>
          r.title?.toLowerCase().includes(q) ||
          r.snippet?.toLowerCase().includes(q) ||
          r.domain?.toLowerCase().includes(q)
      );
    }
    const sorted = [...rows].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "price") cmp = priceValue(a.price) - priceValue(b.price);
      else cmp = String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? ""), "zh-Hant");
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [records, hiddenUrls, category, character, onlyPrice, onlyProducts, query, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  const Th = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th
      className="cursor-pointer select-none px-3 py-2 text-left font-semibold hover:text-brand-600"
      onClick={() => toggleSort(k)}
    >
      {children}
      {sortKey === k ? <span className="ml-1 text-brand-500">{sortAsc ? "▲" : "▼"}</span> : null}
    </th>
  );

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 dark:border-slate-700 p-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜尋標題 / 摘要 / 網域…"
          className="w-56 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5 text-sm"
        >
          {categories.map((c) => (
            <option key={c} value={c}>
              {c === "全部" ? "全部分類" : c}
            </option>
          ))}
        </select>
        {characters.length > 1 && (
          <select
            value={character}
            onChange={(e) => setCharacter(e.target.value)}
            className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5 text-sm"
          >
            {characters.map((c) => (
              <option key={c} value={c}>
                {c === "全部" ? "全部角色" : c}
              </option>
            ))}
          </select>
        )}
        <label className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={onlyPrice} onChange={(e) => setOnlyPrice(e.target.checked)} />
          只看有價格
        </label>
        <label className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={onlyProducts} onChange={(e) => setOnlyProducts(e.target.checked)} />
          只看商品頁
        </label>
        <span className="ml-auto text-xs text-slate-400">顯示 {filtered.length} / {records.length} 筆</span>
      </div>

      <div className="scroll-thin max-h-[560px] overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-300">
            <tr>
              {onToggleSelect && <th className="px-2 py-2" />}
              <Th k="category">分類</Th>
              <Th k="title">標題</Th>
              <Th k="price">價格</Th>
              <Th k="domain">來源</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={`${r.url}-${i}`} className="border-t border-slate-100 dark:border-slate-700 align-top hover:bg-slate-50 dark:bg-slate-900">
                {onToggleSelect && (
                  <td className="px-2 py-2">
                    <input type="checkbox" checked={selectedUrls?.has(r.url) ?? false} onChange={() => onToggleSelect(r.url)} />
                  </td>
                )}
                <td className="px-3 py-2">
                  <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs ${categoryClass(r.category)}`}>
                    {r.category || "其他"}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <a href={r.url} target="_blank" rel="noreferrer" className="font-medium text-brand-700 hover:underline">
                    {r.title}
                  </a>
                  {r.character ? (
                    <span className="ml-1.5 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700">
                      {String(r.character)}
                    </span>
                  ) : null}
                  {r.is_listing ? (
                    <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">列表頁</span>
                  ) : null}
                  {r.snippet ? <p className="mt-0.5 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">{r.snippet}</p> : null}
                </td>
                <td className="whitespace-nowrap px-3 py-2 font-semibold text-rose-600">{r.price || "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500 dark:text-slate-400">{r.domain}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={onToggleSelect ? 5 : 4} className="px-3 py-10 text-center text-slate-400">
                  沒有符合條件的資料
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
