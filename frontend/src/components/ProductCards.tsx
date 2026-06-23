import type { CrawlRecord } from "@/lib/types";
import { categoryClass } from "@/lib/format";

export default function ProductCards({ records }: { records: CrawlRecord[] }) {
  // 優先顯示有價格的周邊/商品
  const items = [...records]
    .filter((r) => (r.price || "").trim() !== "")
    .sort((a, b) => (a.category === "周邊/商品" ? -1 : 0) - (b.category === "周邊/商品" ? -1 : 0))
    .slice(0, 12);

  if (items.length === 0) {
    return <p className="text-sm text-slate-400">這次沒有偵測到帶價格的商品。</p>;
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {items.map((r, i) => (
        <a
          key={`${r.url}-${i}`}
          href={r.url}
          target="_blank"
          rel="noreferrer"
          className="group flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md"
        >
          <div className="aspect-square w-full overflow-hidden bg-slate-100">
            {r.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={r.image_url}
                alt={r.title}
                className="h-full w-full object-cover transition group-hover:scale-105"
                loading="lazy"
              />
            ) : (
              <div className="grid h-full place-items-center text-slate-300">無圖片</div>
            )}
          </div>
          <div className="flex flex-1 flex-col p-3">
            <span className={`mb-1 w-fit rounded-full border px-2 py-0.5 text-[10px] ${categoryClass(r.category)}`}>
              {r.category || "其他"}
            </span>
            <p className="line-clamp-2 text-sm font-medium text-slate-700">{r.title}</p>
            <div className="mt-auto flex items-center justify-between pt-2">
              <span className="font-bold text-rose-600">{r.price}</span>
              <span className="text-[10px] text-slate-400">{r.domain}</span>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
