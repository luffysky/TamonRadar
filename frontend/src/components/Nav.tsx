"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
            onClick={() => setOpen((o) => !o)}
            aria-label="選單"
            aria-expanded={open}
            className="grid h-9 w-9 place-items-center rounded-md text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            {open ? "✕" : "☰"}
          </button>
        </div>
      </div>

      {/* 手機展開選單 — 平滑展開(grid-rows 0fr→1fr) */}
      <div className={`grid overflow-hidden transition-all duration-300 ease-out md:hidden ${open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
        <div className="overflow-hidden">
          <nav className="border-t border-slate-200 bg-white px-4 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex flex-col gap-0.5">
              {visible.map((l, i) => (
                <Link
                  key={l.href}
                  href={l.href}
                  onClick={() => setOpen(false)}
                  style={{ transitionDelay: open ? `${i * 25}ms` : "0ms" }}
                  className={`${linkCls(l.href)} transition-all ${open ? "translate-x-0 opacity-100" : "-translate-x-2 opacity-0"}`}
                >
                  {l.label}
                </Link>
              ))}
              <div className="my-1 border-t border-slate-100 dark:border-slate-700" />
              {user ? (
                <button onClick={() => { setOpen(false); signOut(); }} className="rounded-md px-3 py-1.5 text-left text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
                  登出({user.email})
                </button>
              ) : (
                <Link href="/login" onClick={() => setOpen(false)} className="rounded-md bg-brand-600 px-3 py-1.5 text-center text-white hover:bg-brand-700">登入</Link>
              )}
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
}
