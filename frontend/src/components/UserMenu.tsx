"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { User, LayoutDashboard, Heart, PenSquare, Settings, Shield, LogOut, ChevronDown } from "lucide-react";
import { useAuth } from "./AuthProvider";
import { ADMIN_BASE } from "@/lib/admin";

export default function UserMenu() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  if (!user) return null;
  const name = user.username || user.email.split("@")[0];

  const items = [
    { href: "/settings", label: "個人資料 / 設定", icon: Settings },
    { href: "/dashboard", label: "我的儀表板", icon: LayoutDashboard },
    { href: "/blog/mine", label: "我的部落格", icon: PenSquare },
    { href: "/favorites", label: "我的收藏", icon: Heart },
  ];

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-full border border-slate-200 py-1 pl-1 pr-2 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700"
      >
        <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200">
          <User className="h-4 w-4" />
        </span>
        <span className="hidden max-w-[120px] truncate text-sm text-slate-700 dark:text-slate-200 sm:inline">{name}</span>
        <ChevronDown className={`h-4 w-4 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-56 origin-top-right animate-fade-in rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-700 dark:bg-slate-800">
          <div className="border-b border-slate-100 px-3 py-2 dark:border-slate-700">
            <p className="truncate text-sm font-semibold text-slate-700 dark:text-slate-200">{name}</p>
            <p className="truncate text-xs text-slate-400">{user.email}</p>
            <div className="mt-1 flex gap-1">
              {user.privileged && <span className="rounded-full bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-700">特權</span>}
              {user.is_admin && <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">管理員</span>}
              {!user.privileged && !user.is_admin && <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700">{user.plan || "free"}</span>}
            </div>
          </div>
          {items.map((it) => (
            <Link key={it.href} href={it.href} onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
              <it.icon className="h-4 w-4" /> {it.label}
            </Link>
          ))}
          {user.is_admin && (
            <>
              <div className="my-1 border-t border-slate-100 dark:border-slate-700" />
              <Link href={ADMIN_BASE} onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-amber-700 hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-slate-700">
                <Shield className="h-4 w-4" /> 管理後台(CRM / ERP)
              </Link>
              <Link href={`${ADMIN_BASE}/ops`} onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-amber-700 hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-slate-700">
                <Shield className="h-4 w-4" /> 營運管理
              </Link>
            </>
          )}
          <button onClick={() => { setOpen(false); signOut(); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-rose-600 hover:bg-rose-50 dark:hover:bg-slate-700">
            <LogOut className="h-4 w-4" /> 登出
          </button>
        </div>
      )}
    </div>
  );
}
