"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";

export default function Nav() {
  const { user, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold text-brand-600">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-base text-white">📡</span>
          <span>TamonRadar</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/" className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100">搜尋</Link>
          <Link href="/history" className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100">歷史紀錄</Link>
          <Link href="/about" className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100">如何運作</Link>
          {user ? (
            <div className="ml-2 flex items-center gap-2 border-l border-slate-200 pl-2">
              <span className="hidden text-xs text-slate-400 sm:inline">{user.email}</span>
              <button
                onClick={signOut}
                className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100"
              >
                登出
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="ml-2 rounded-md bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700"
            >
              登入
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
