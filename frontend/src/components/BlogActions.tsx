"use client";

import Link from "next/link";
import { PenSquare } from "lucide-react";
import { useAuth } from "./AuthProvider";

export default function BlogActions() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-2">
      <Link href="/blog/mine" className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">我的部落格</Link>
      <Link href="/blog/new" className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
        <PenSquare className="h-4 w-4" /> 寫文章
      </Link>
    </div>
  );
}
