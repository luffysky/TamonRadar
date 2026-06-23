"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";
import ThemeToggle from "./ThemeToggle";

export default function Nav() {
  const { user, signOut } = useAuth();
  const link = "rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700";

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/70 backdrop-blur-lg dark:border-slate-700 dark:bg-slate-900/70">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-bold text-brand-600 dark:text-brand-300">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-base text-white shadow-sm">📡</span>
          <span>TamonRadar</span>
        </Link>
        <nav className="flex flex-wrap items-center justify-end gap-1 text-sm">
          <Link href="/" className={link}>搜尋</Link>
          <Link href="/history" className={link}>歷史</Link>
          {user && <Link href="/schedules" className={link}>排程</Link>}
          {user && <Link href="/watches" className={link}>監看</Link>}
          {user && <Link href="/settings" className={link}>設定</Link>}
          {user?.is_admin && <Link href="/admin" className="rounded-md px-3 py-1.5 font-medium text-amber-600 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-950">管理</Link>}
          <Link href="/about" className={link}>說明</Link>
          <ThemeToggle />
          {user ? (
            <div className="ml-1 flex items-center gap-2 border-l border-slate-200 pl-2 dark:border-slate-700">
              <span className="hidden text-xs text-slate-400 sm:inline">{user.email}</span>
              <button onClick={signOut} className={link}>登出</button>
            </div>
          ) : (
            <Link href="/login" className="ml-1 rounded-md bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700">
              登入
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
