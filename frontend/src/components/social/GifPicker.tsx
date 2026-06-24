"use client";

import { useEffect, useRef, useState } from "react";
import { Search, X, Loader2 } from "lucide-react";

const GIPHY_API_KEY = process.env.NEXT_PUBLIC_GIPHY_API_KEY ?? "";
const PER_PAGE = 15;

interface GifResult {
  id: string;
  images: {
    fixed_height_small: { url: string };
    original: { url: string };
  };
  title: string;
}

export default function GifPicker({
  onSelect,
  onClose,
}: {
  onSelect: (url: string) => void;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<"gifs" | "stickers">("gifs");
  const [query, setQuery] = useState("");
  const [gifs, setGifs] = useState<GifResult[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  async function fetchGifs(q: string) {
    if (!GIPHY_API_KEY) {
      setGifs([]);
      return;
    }
    setLoading(true);
    try {
      const base = `https://api.giphy.com/v1/${kind}`;
      const url = q.trim()
        ? `${base}/search?api_key=${GIPHY_API_KEY}&q=${encodeURIComponent(q)}&limit=${PER_PAGE}&rating=g`
        : `${base}/trending?api_key=${GIPHY_API_KEY}&limit=${PER_PAGE}&rating=g`;
      const res = await fetch(url);
      const data = (await res.json()) as { data: GifResult[] };
      setGifs(data.data ?? []);
    } catch {
      setGifs([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchGifs(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  function onQuery(v: string) {
    setQuery(v);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => fetchGifs(v), 350);
  }

  return (
    <div className="absolute bottom-12 left-0 z-30 w-[min(22rem,calc(100vw-3rem))] rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl dark:border-slate-700 dark:bg-slate-800">
      <div className="mb-2 flex items-center gap-2">
        <div className="flex rounded-lg bg-slate-100 p-0.5 text-xs dark:bg-slate-700">
          {(["gifs", "stickers"] as const).map((k) => (
            <button key={k} onClick={() => setKind(k)} className={`rounded-md px-2 py-1 ${kind === k ? "bg-white text-brand-600 shadow-sm dark:bg-slate-800" : "text-slate-500"}`}>
              {k === "gifs" ? "GIF" : "貼圖"}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="ml-auto rounded-md p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="relative mb-2">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
        <input
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={GIPHY_API_KEY ? "搜尋…" : "未設定 GIPHY 金鑰"}
          disabled={!GIPHY_API_KEY}
          className="w-full rounded-lg border border-slate-300 py-1.5 pl-8 pr-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600"
        />
      </div>

      <div className="grid h-56 grid-cols-3 gap-1.5 overflow-auto">
        {loading ? (
          <div className="col-span-3 grid place-items-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin" /></div>
        ) : gifs.length === 0 ? (
          <p className="col-span-3 mt-6 text-center text-xs text-slate-400">
            {GIPHY_API_KEY ? "沒有結果" : "請在環境變數設定 NEXT_PUBLIC_GIPHY_API_KEY"}
          </p>
        ) : (
          gifs.map((g) => (
            <button key={g.id} onClick={() => onSelect(g.images.original.url)} className="overflow-hidden rounded-lg hover:ring-2 hover:ring-brand-400">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={g.images.fixed_height_small.url} alt={g.title} className="h-24 w-full object-cover" loading="lazy" />
            </button>
          ))
        )}
      </div>
      <p className="mt-1 text-right text-[10px] text-slate-300">Powered by GIPHY</p>
    </div>
  );
}
