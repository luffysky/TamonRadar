"use client";

import { useEffect, useState } from "react";
import {
  getWatches, createWatch, updateWatch, deleteWatch, checkWatch,
  type Watch, type WatchInput,
} from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";

const STATUS: Record<string, { label: string; cls: string }> = {
  available: { label: "可能可買!", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" },
  unavailable: { label: "目前無貨/未開賣", cls: "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400" },
  unknown: { label: "尚未判斷", cls: "bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500" },
  watching: { label: "監看內容中", cls: "bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300" },
};

export default function WatchesPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [watches, setWatches] = useState<Watch[]>([]);
  const [editId, setEditId] = useState<number | null>(null);
  const [edit, setEdit] = useState<{ interval: number; target: string; notifyOn: string[] }>({ interval: 5, target: "", notifyOn: [] });
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [interval, setIntervalMin] = useState(5);
  const [targetPrice, setTargetPrice] = useState("");
  const [notifyOn, setNotifyOn] = useState<string[]>(["new", "removed", "price", "restock"]);
  const [busy, setBusy] = useState(false);

  function toggleNotify(k: string) {
    setNotifyOn((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]));
  }

  async function reload() {
    try {
      setWatches((await getWatches()).watches);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (!user) return;
    reload();
    // 自動更新:每 20 秒重抓監看狀態,不用手動重新整理
    const t = setInterval(reload, 20000);
    return () => clearInterval(t);
  }, [user]);

  if (!ready || !user) {
    return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  }

  async function add() {
    if (!url.trim().startsWith("http")) {
      toast("請輸入有效的網址", "error");
      return;
    }
    setBusy(true);
    try {
      const data: WatchInput = {
        name: name.trim(), url: url.trim(),
        available_keywords: [], unavailable_keywords: [],
        interval_minutes: interval, enabled: true,
        target_price: targetPrice.trim() ? Number(targetPrice.replace(/[^0-9]/g, "")) : null,
        notify_on: notifyOn,
      };
      await createWatch(data);
      setName(""); setUrl(""); setTargetPrice("");
      await reload();
      toast("已新增監看,會自動定時檢查", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "新增失敗", "error");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(w: Watch) {
    setEditId(w.id);
    setEdit({ interval: w.interval_minutes, target: w.target_price ? String(w.target_price) : "", notifyOn: w.notify_on ?? ["new", "removed", "price", "restock"] });
  }
  async function saveEdit(w: Watch) {
    await updateWatch(w.id, {
      ...w,
      interval_minutes: Math.max(1, Math.min(edit.interval, 1440)),
      target_price: edit.target.trim() ? Number(edit.target.replace(/[^0-9]/g, "")) : null,
      notify_on: edit.notifyOn,
    });
    setEditId(null);
    await reload();
    toast("已更新監看設定", "success");
  }

  async function toggle(w: Watch) {
    await updateWatch(w.id, { ...w, enabled: !w.enabled });
    reload();
  }
  async function remove(id: number) {
    await deleteWatch(id);
    reload();
    toast("已刪除", "info");
  }
  async function checkNow(id: number) {
    await checkWatch(id);
    toast("已在背景檢查一次,有開賣會推播", "success");
    setTimeout(reload, 3000);
  }

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">監看 · 到貨/開賣通知</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          貼上商品/票券網址,系統定時檢查,**售完→補貨**、未開賣→開賣、或**降到目標價**時,立刻推播到你的 Discord / Telegram。
          (記得先到「設定」設好通知管道)
        </p>
        <p className="mt-1 text-xs text-slate-400">
          內建判斷「售完/缺貨/補貨中 ↔ 現貨/加入購物車」字眼,免設定就會用;也會讀頁面內嵌 JSON(動態庫存)。最快每 1 分鐘檢查。
        </p>
      </div>

      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="名稱(例:XXX 演唱會門票)" className={field} />
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://要監看的網址" className={field} />
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1 text-sm">
            <span className="text-slate-600 dark:text-slate-300">通知條件(可複選,一個監看全包)</span>
            <div className="flex flex-wrap gap-3 pt-1.5">
              {[["restock", "補貨/到貨"], ["new", "新增商品"], ["removed", "下架"], ["price", "價格變動"]].map(([k, label]) => (
                <label key={k} className="flex items-center gap-1.5">
                  <input type="checkbox" checked={notifyOn.includes(k)} onChange={() => toggleNotify(k)} /> {label}
                </label>
              ))}
            </div>
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-600 dark:text-slate-300">每隔幾分鐘檢查</span>
            <input type="number" min={1} max={1440} value={interval} onChange={(e) => setIntervalMin(Number(e.target.value))} className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 dark:border-slate-600" />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-slate-600 dark:text-slate-300">目標價(選填,低於就通知)</span>
            <input value={targetPrice} onChange={(e) => setTargetPrice(e.target.value)} placeholder="NT$" className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 dark:border-slate-600" />
          </label>
          <button onClick={add} disabled={busy} className="ml-auto rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            新增監看
          </button>
        </div>
        <p className="text-xs text-slate-400">
          ⚠️ 用於「提醒你去買」,不會自動下單。需 JS 才顯示庫存的網站(部分票務平台)可能偵測不到。請勿設太短間隔以免被網站封鎖。
        </p>
      </div>

      <div className="space-y-3">
        {watches.length === 0 && <p className="text-sm text-slate-400">還沒有監看項目。</p>}
        {watches.map((w) => {
          const st = STATUS[w.last_status] ?? STATUS.unknown;
          return (
            <div key={w.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{w.name || w.url}</p>
                <a href={w.url} target="_blank" rel="noreferrer" className="block truncate text-xs text-brand-600 hover:underline dark:text-brand-300">{w.url}</a>
                <p className="text-xs text-slate-400">
                  每 {w.interval_minutes} 分鐘{w.last_checked ? ` · 上次 ${new Date(w.last_checked).toLocaleString("zh-TW")}` : " · 尚未檢查"}
                  {w.target_price ? ` · 目標 NT$${w.target_price}${w.last_price_twd ? `(現 NT$${w.last_price_twd})` : ""}` : ""}
                </p>
                {w.last_error && <p className="mt-0.5 break-words text-xs text-rose-500">⚠️ 上次檢查失敗:{w.last_error}</p>}
              </div>
              <span className={`rounded-full px-2 py-0.5 text-xs ${st.cls}`}>{st.label}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${w.enabled ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"}`}>
                {w.enabled ? "監看中" : "已停用"}
              </span>
              {w.cta_url && (
                <a href={w.cta_url} target="_blank" rel="noreferrer" className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700">
                  {w.cta_text || "前往購買"} →
                </a>
              )}
              <button onClick={() => checkNow(w.id)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">立即檢查</button>
              <button onClick={() => (editId === w.id ? setEditId(null) : startEdit(w))} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">{editId === w.id ? "收起" : "編輯"}</button>
              <button onClick={() => toggle(w)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">{w.enabled ? "停用" : "啟用"}</button>
              <button onClick={() => remove(w.id)} className="rounded-md border border-rose-200 px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50">刪除</button>
            </div>

            {editId === w.id && (
              <div className="mt-3 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-3 dark:border-slate-700">
                <label className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">每隔幾分鐘
                  <input type="number" min={1} max={1440} value={edit.interval} onChange={(e) => setEdit({ ...edit, interval: Number(e.target.value) })} className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">目標價
                  <input value={edit.target} onChange={(e) => setEdit({ ...edit, target: e.target.value })} placeholder="NT$" className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600" />
                </label>
                <div className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">通知條件
                  <div className="flex flex-wrap gap-2 pt-1">
                    {[["restock", "補貨"], ["new", "新增"], ["removed", "下架"], ["price", "改價"]].map(([k, label]) => (
                      <label key={k} className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-300">
                        <input type="checkbox" checked={edit.notifyOn.includes(k)} onChange={() => setEdit({ ...edit, notifyOn: edit.notifyOn.includes(k) ? edit.notifyOn.filter((x) => x !== k) : [...edit.notifyOn, k] })} /> {label}
                      </label>
                    ))}
                  </div>
                </div>
                <button onClick={() => saveEdit(w)} className="ml-auto rounded-lg bg-brand-600 px-4 py-1.5 text-sm text-white hover:bg-brand-700">儲存</button>
              </div>
            )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
