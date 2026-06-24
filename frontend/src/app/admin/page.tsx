"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getAdminStats, getAdminUsers, setUserPlan, setUserPrivilege, setupTelegramBot, setupDiscordBot,
  type AdminStats, type AdminUser,
} from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { ADMIN_BASE } from "@/lib/admin";

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-bold text-brand-600 dark:text-brand-300">{value}</div>
    </div>
  );
}

export default function AdminPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [denied, setDenied] = useState(false);
  const [q, setQ] = useState("");

  async function load() {
    try {
      const [s, u] = await Promise.all([getAdminStats(), getAdminUsers()]);
      setStats(s);
      setUsers(u.users);
    } catch (e) {
      if (e instanceof Error && e.message !== "UNAUTHORIZED") setDenied(true);
    }
  }

  useEffect(() => {
    if (user) load();
  }, [user]);

  if (!ready || !user) {
    return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  }
  if (denied || (user && !user.is_admin)) {
    return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;
  }

  async function togglePlan(u: AdminUser) {
    const next = u.plan === "pro" ? "free" : "pro";
    try {
      await setUserPlan(u.id, next);
      toast(`${u.email} → ${next}`, "success");
      load();
    } catch {
      toast("更新失敗", "error");
    }
  }

  async function togglePriv(u: AdminUser) {
    try {
      await setUserPrivilege(u.id, !u.privileged);
      toast(u.privileged ? "已取消特權" : "已給予特權", "success");
      load();
    } catch {
      toast("更新失敗", "error");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">管理員後台</h1>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={async () => { try { const r = await setupTelegramBot(); toast(r.ok ? "Telegram webhook 已設定" : `失敗:${r.error ?? ""}`, r.ok ? "success" : "error"); } catch { toast("設定失敗", "error"); } }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"
          >
            設定 Telegram 機器人
          </button>
          <button
            onClick={async () => { try { const r = await setupDiscordBot(); toast(r.ok ? "Discord 指令已註冊" : `失敗:${r.error ?? ""}`, r.ok ? "success" : "error"); } catch { toast("設定失敗", "error"); } }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"
          >
            註冊 Discord 指令
          </button>
          <Link href={`${ADMIN_BASE}/blog`} className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">部落格管理</Link>
        </div>
      </div>

      {stats && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="總使用者" value={stats.total_users} />
            <Stat label="AI 總呼叫次數" value={stats.total_ai_calls} />
            <Stat label="搜尋次數" value={stats.total_runs} />
            <Stat label="近 7 天新註冊" value={stats.new_users_7d} />
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="監看數" value={stats.total_watches} />
            <Stat label="排程數" value={stats.total_schedules} />
            <Stat label="文章數" value={stats.total_posts} />
            <Stat label="討論主題/回覆" value={`${stats.total_threads}/${stats.total_replies}`} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">登入方式分布</p>
              {Object.entries(stats.by_provider).map(([k, v]) => (
                <div key={k} className="flex justify-between text-slate-600 dark:text-slate-300"><span>{k}</span><span>{v}</span></div>
              ))}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">方案分布</p>
              {Object.entries(stats.by_plan).map(([k, v]) => (
                <div key={k} className="flex justify-between text-slate-600 dark:text-slate-300"><span>{k}</span><span>{v}</span></div>
              ))}
            </div>
          </div>

          {stats.top_ai_users.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">AI 用量排行</p>
              {stats.top_ai_users.map((u) => (
                <div key={u.email} className="flex justify-between text-slate-600 dark:text-slate-300">
                  <span className="truncate">{u.email}</span><span>{u.ai_used}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="搜尋 email…"
        className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600"
      />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="scroll-thin overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 dark:bg-slate-900 dark:text-slate-300">
              <tr>
                <th className="px-3 py-2 text-left">名稱</th>
                <th className="px-3 py-2 text-left">Email</th>
                <th className="px-3 py-2 text-left">登入</th>
                <th className="px-3 py-2 text-left">方案</th>
                <th className="px-3 py-2 text-right">AI 用量</th>
                <th className="px-3 py-2 text-left">註冊時間</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {users.filter((u) => u.email.toLowerCase().includes(q.toLowerCase()) || (u.username ?? "").toLowerCase().includes(q.toLowerCase())).map((u) => (
                <tr key={u.id} className="border-t border-slate-100 dark:border-slate-700">
                  <td className="px-3 py-2 font-medium text-slate-700 dark:text-slate-200">
                    {u.username || "—"}
                    {u.privileged && <span className="ml-1.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700">特權</span>}
                  </td>
                  <td className="px-3 py-2">
                    <Link href={`${ADMIN_BASE}/users/${u.id}`} className="text-brand-600 hover:underline dark:text-brand-300">{u.email}</Link>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">{u.provider}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${u.plan === "pro" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"}`}>{u.plan}</span>
                  </td>
                  <td className="px-3 py-2 text-right text-slate-600 dark:text-slate-300">{u.ai_used}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{u.created_at ? new Date(u.created_at).toLocaleDateString("zh-TW") : "-"}</td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => togglePlan(u)} className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">
                        {u.plan === "pro" ? "降 free" : "升 pro"}
                      </button>
                      <button onClick={() => togglePriv(u)} className={`rounded-md border px-2 py-1 text-xs ${u.privileged ? "border-violet-300 text-violet-600 hover:bg-violet-50" : "border-slate-300 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"}`}>
                        {u.privileged ? "取消特權" : "給特權"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
