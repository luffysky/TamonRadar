"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useAuth } from "./AuthProvider";
import ThemeToggle from "./ThemeToggle";

interface NavLink {
  href: string;
  label: string;
  show: "all" | "auth" | "admin";
}

const LINKS: NavLink[] = [
  { href: "/", label: "搜尋", show: "all" },
  { href: "/history", label: "歷史", show: "all" },
  { href: "/blog", label: "部落格", show: "all" },
  { href: "/forum", label: "討論區", show: "all" },
  { href: "/schedules", label: "排程", show: "auth" },
  { href: "/watches", label: "監看", show: "auth" },
  { href: "/settings", label: "設定", show: "auth" },
  { href: "/admin", label: "管理", show: "admin" },
  { href: "/about", label: "說明", show: "all" },
];

export default function Nav() {
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const visible = LINKS.filter((l) =>
    l.show === "all" ? true : l.show === "auth" ? !!user : !!user?.is_admin
  );

  const linkCls = (href: string) =>
    `rounded-md px-3 py-1.5 ${
      pathname === href
        ? "bg-brand-50 text-brand-700 dark:bg-slate-700 dark:text-brand-300"
        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
    }`;

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/70 backdrop-blur-lg dark:border-slate-700 dark:bg-slate-900/70">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3">
        <Link href="/" onClick={() => setOpen(false)} className="flex shrink-0 items-center gap-2 font-bold text-brand-600 dark:text-brand-300">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-mark.png" alt="TamonRadar" className="h-9 w-9 rounded-lg object-cover shadow-sm ring-1 ring-slate-200 dark:ring-slate-700" />
          <span>TamonRadar</span>
        </Link>

        {/* 桌機:橫排 */}
        <nav className="hidden items-center gap-1 text-sm md:flex">
          {visible.map((l) => (
            <Link key={l.href} href={l.href} className={linkCls(l.href)}>{l.label}</Link>
          ))}
          <ThemeToggle />
          {user ? (
            <div className="ml-1 flex items-center gap-2 border-l border-slate-200 pl-2 dark:border-slate-700">
              <span className="hidden text-xs text-slate-400 lg:inline">{user.email}</span>
              <button onClick={signOut} className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">登出</button>
            </div>
          ) : (
            <Link href="/login" className="ml-1 rounded-md bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700">登入</Link>
          )}
        </nav>

        {/* 手機:主題鈕 + 漢堡 */}
        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <button
            onClick={() => setOpen(true)}
            aria-label="選單"
            aria-expanded={open}
            className="grid h-9 w-9 place-items-center rounded-md text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* 手機側邊抽屜:從右往左滑入、滿視口高 */}
      <div
        onClick={() => setOpen(false)}
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 md:hidden ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-[100dvh] w-72 max-w-[82vw] transform flex-col border-l border-slate-200 bg-white shadow-2xl transition-transform duration-300 ease-out md:hidden dark:border-slate-700 dark:bg-slate-900 ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <span className="font-bold text-brand-600 dark:text-brand-300">選單</span>
          <button onClick={() => setOpen(false)} aria-label="關閉" className="grid h-9 w-9 place-items-center rounded-md text-slate-500 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex flex-1 flex-col gap-0.5 overflow-auto p-3 text-sm">
          {visible.map((l) => (
            <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className={`${linkCls(l.href)} py-2.5`}>
              {l.label}
            </Link>
          ))}
          <div className="my-2 border-t border-slate-100 dark:border-slate-700" />
          {user ? (
            <button onClick={() => { setOpen(false); signOut(); }} className="rounded-md px-3 py-2.5 text-left text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
              登出({user.email})
            </button>
          ) : (
            <Link href="/login" onClick={() => setOpen(false)} className="rounded-md bg-brand-600 px-3 py-2.5 text-center text-white hover:bg-brand-700">登入</Link>
          )}
        </div>
      </aside>
    </header>
  );
}
