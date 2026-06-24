"use client";

import { useEffect, useState } from "react";
import { getFavorites, setFavoriteTarget, removeFavorite, type Favorite } from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import PriceTrend from "@/components/PriceTrend";
import ProductImage from "@/components/ProductImage";

export default function FavoritesPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [favs, setFavs] = useState<Favorite[]>([]);

  async function load() {
    try {
      setFavs((await getFavorites()).favorites);
    } catch {
      /* ignore */
    }
  }
  useEffect(() => { if (user) load(); }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  async function saveTarget(f: Favorite, v: string) {
    const t = v.trim() === "" ? null : Number(v.replace(/[^0-9]/g, ""));
    await setFavoriteTarget(f.id, t);
    toast(t ? `已設定目標價 NT$${t}` : "已清除目標價", "success");
    load();
  }
  async function remove(id: number) {
    await removeFavorite(id);
    load();
    toast("已移除收藏", "info");
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">我的收藏</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          設定目標價,排程搜尋到該商品降到目標價時會推播通知(需設好通知管道)。
        </p>
      </div>

      {favs.length === 0 ? (
        <p className="text-sm text-slate-400">還沒有收藏。在搜尋結果的商品卡按愛心即可收藏。</p>
      ) : (
        <div className="space-y-3">
          {favs.map((f) => (
            <div key={f.id} className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <a href={f.url} target="_blank" rel="noreferrer" className="h-16 w-16 shrink-0 overflow-hidden rounded-lg">
                <ProductImage src={f.image_url} alt={f.title} />
              </a>
              <div className="min-w-0 flex-1">
                <a href={f.url} target="_blank" rel="noreferrer" className="line-clamp-1 text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">{f.title || f.url}</a>
                <p className="text-xs text-slate-400">{f.domain} · 收藏時 {f.price || "無價格"}</p>
                <div className="mt-1"><PriceTrend url={f.url} /></div>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs text-slate-500 dark:text-slate-400">目標價</label>
                <input
                  defaultValue={f.target_twd ?? ""}
                  onBlur={(e) => saveTarget(f, e.target.value)}
                  placeholder="NT$"
                  className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600"
                />
                <button onClick={() => remove(f.id)} className="rounded-md border border-rose-200 px-3 py-1 text-xs text-rose-600 hover:bg-rose-50">移除</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
