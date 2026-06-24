"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useRequireAuth } from "@/components/AuthProvider";
import { getAdminCrawls, type CrawlLog } from "@/lib/api";

export default function AdminCrawlsPage() {
  const { user, ready } = useRequireAuth();
  const [crawls, setCrawls] = useState<CrawlLog[]>([]);

  useEffect(() => {
    if (user) getAdminCrawls().then((d) => setCrawls(d.crawls)).catch(() => {});
  }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">爬取檢核(全站)</h1>

      <div className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="font-semibold">所有人的每一輪爬取都自動套用同一套規則:</p>
          <p className="mt-0.5 text-xs">✓ 遵守 robots.txt ✓ 封鎖登入牆/禁爬站 ✓ 自動節流 ✓ 僅抓公開資料 ✓ 每日配額。這些是程式層強制,不分使用者、無法繞過。</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="scroll-thin overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 dark:bg-slate-900 dark:text-slate-300">
              <tr>
                <th className="px-3 py-2 text-left">使用者</th>
                <th className="px-3 py-2 text-left">模式</th>
                <th className="px-3 py-2 text-left">爬了什麼</th>
                <th className="px-3 py-2 text-right">筆數</th>
                <th className="px-3 py-2 text-left">時間</th>
                <th className="px-3 py-2 text-center">合規</th>
              </tr>
            </thead>
            <tbody>
              {crawls.length === 0 ? (
                <tr><td colSpan={6} className="px-3 py-10 text-center text-slate-400">尚無爬取紀錄</td></tr>
              ) : crawls.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 dark:border-slate-700">
                  <td className="px-3 py-2"><span className="font-medium text-slate-700 dark:text-slate-200">{c.user}</span><span className="block text-xs text-slate-400">{c.email}</span></td>
                  <td className="px-3 py-2"><span className={`rounded-full px-2 py-0.5 text-xs ${c.mode === "整站爬" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300"}`}>{c.mode}</span></td>
                  <td className="px-3 py-2 max-w-[320px] truncate text-slate-600 dark:text-slate-300" title={c.target}>{c.target || "—"}</td>
                  <td className="px-3 py-2 text-right text-slate-600 dark:text-slate-300">{c.total}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{c.finished_at ? new Date(c.finished_at).toLocaleString("zh-TW") : "-"}</td>
                  <td className="px-3 py-2 text-center"><ShieldCheck className="mx-auto h-4 w-4 text-emerald-500" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
