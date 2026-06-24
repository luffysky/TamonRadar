"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getForumCategories, getForumThreads, type ForumCategory, type ForumThread } from "@/lib/api";

export default function ForumPage() {
  const [cats, setCats] = useState<ForumCategory[]>([]);
  const [recent, setRecent] = useState<ForumThread[]>([]);

  useEffect(() => {
    getForumCategories().then((d) => setCats(d.categories)).catch(() => {});
    getForumThreads().then((d) => setRecent(d.threads.slice(0, 8))).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">討論區</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">選個分類聊聊,或看看最新討論。</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {cats.map((c) => (
          <Link key={c.slug} href={`/forum/${c.slug}`} className="card flex items-center gap-3 p-4 transition hover:-translate-y-0.5 hover:shadow-lg">
            <span className="text-2xl">{c.emoji}</span>
            <span className="font-medium text-slate-700 dark:text-slate-200">{c.label}</span>
          </Link>
        ))}
      </div>

      {recent.length > 0 && (
        <div>
          <h2 className="mb-2 text-lg font-semibold text-slate-700 dark:text-slate-200">最新討論</h2>
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white dark:divide-slate-700 dark:border-slate-700 dark:bg-slate-800">
            {recent.map((t) => (
              <Link key={t.id} href={`/forum/thread/${t.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{t.title}</p>
                  <p className="text-xs text-slate-400">{t.author} · 回覆 {t.reply_count}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
