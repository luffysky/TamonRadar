"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, Megaphone, Shield } from "lucide-react";
import { ADMIN_BASE } from "@/lib/admin";

const NAV = [
  { href: ADMIN_BASE, label: "總覽", icon: LayoutDashboard },
  { href: `${ADMIN_BASE}/ops`, label: "營運管理", icon: Megaphone },
  { href: `${ADMIN_BASE}/blog`, label: "部落格管理", icon: FileText },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="grid gap-5 lg:grid-cols-[210px_1fr]">
      <aside className="lg:sticky lg:top-20 lg:h-fit">
        <div className="mb-3 flex items-center gap-2 px-2 text-sm font-bold text-slate-700 dark:text-slate-200">
          <Shield className="h-4 w-4 text-amber-500" /> 管理後台
        </div>
        <nav className="scroll-thin flex gap-1 overflow-x-auto lg:flex-col lg:gap-0.5">
          {NAV.map((n) => {
            const active = n.href === ADMIN_BASE ? pathname === ADMIN_BASE : pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-brand-50 font-medium text-brand-700 dark:bg-slate-700 dark:text-brand-300"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                }`}
              >
                <n.icon className="h-4 w-4" /> {n.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
