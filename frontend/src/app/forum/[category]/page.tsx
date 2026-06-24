"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getForumCategories, getForumThreads, createThread,
  type ForumCategory, type ForumThread,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import RichTextEditor from "@/components/social/RichTextEditor";

export default function ForumCategoryPage({ params }: { params: { category: string } }) {
  const { user } = useAuth();
  const toast = useToast();
  const [cat, setCat] = useState<ForumCategory | null>(null);
  const [threads, setThreads] = useState<ForumThread[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  async function load() {
    const t = await getForumThreads(params.category);
    setThreads(t.threads);
  }

  useEffect(() => {
    getForumCategories().then((d) => setCat(d.categories.find((c) => c.slug === params.category) ?? null)).catch(() => {});
    load().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.category]);

  async function submit() {
    if (!title.trim()) { toast("請輸入標題", "error"); return; }
    try {
      await createThread(params.category, title.trim(), content);
      setTitle(""); setContent(""); setShowForm(false);
      load();
      toast("已發表", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "發表失敗", "error");
    }
  }

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
          {cat ? `${cat.emoji} ${cat.label}` : params.category}
        </h1>
        <div className="flex gap-2">
          <Link href="/forum" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">← 所有分類</Link>
          {user ? (
            <button onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">發表主題</button>
          ) : (
            <Link href="/login" className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">登入後發表</Link>
          )}
        </div>
      </div>

      {showForm && user && (
        <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="標題" className={field} />
          <RichTextEditor content={content} onChange={setContent} placeholder="想說什麼…" />
          <button onClick={submit} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">送出</button>
        </div>
      )}

      <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white dark:divide-slate-700 dark:border-slate-700 dark:bg-slate-800">
        {threads.length === 0 && <p className="px-4 py-6 text-sm text-slate-400">這個分類還沒有討論,來當第一個吧。</p>}
        {threads.map((t) => (
          <Link key={t.id} href={`/forum/thread/${t.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{t.title}</p>
              <p className="text-xs text-slate-400">{t.author} · {t.last_reply_at ? new Date(t.last_reply_at).toLocaleString("zh-TW") : ""}</p>
            </div>
            <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-700 dark:text-slate-400">{t.reply_count} 回覆</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
