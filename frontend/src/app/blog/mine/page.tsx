"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PenSquare, Pencil, Trash2 } from "lucide-react";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { getMyPosts, myDeletePost, type BlogPost } from "@/lib/api";

export default function MyBlogPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [posts, setPosts] = useState<BlogPost[]>([]);

  function load() { getMyPosts().then((d) => setPosts(d.posts)).catch(() => {}); }
  useEffect(() => { if (user) load(); }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  async function remove(id: number) {
    if (!confirm("確定刪除這篇文章?")) return;
    await myDeletePost(id);
    toast("已刪除", "info");
    load();
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">我的部落格</h1>
        <Link href="/blog/new" className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          <PenSquare className="h-4 w-4" /> 寫文章
        </Link>
      </div>

      {posts.length === 0 ? (
        <p className="text-sm text-slate-400">還沒有文章,點「寫文章」開始吧。</p>
      ) : (
        <div className="space-y-2">
          {posts.map((p) => (
            <div key={p.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium text-slate-700 dark:text-slate-200">{p.title}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] ${p.published ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500 dark:bg-slate-700"}`}>
                    {p.published ? "已發佈" : "草稿"}
                  </span>
                </div>
                <p className="truncate text-xs text-slate-400">{p.category || "未分類"} · {p.updated_at ? new Date(p.updated_at).toLocaleDateString("zh-TW") : ""}</p>
              </div>
              {p.published && <Link href={`/blog/${p.slug}`} className="shrink-0 text-xs text-brand-600 hover:underline dark:text-brand-300">檢視</Link>}
              <Link href={`/blog/edit/${p.id}`} className="shrink-0 rounded-md border border-slate-300 p-1.5 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"><Pencil className="h-4 w-4" /></Link>
              <button onClick={() => remove(p.id)} className="shrink-0 rounded-md border border-rose-200 p-1.5 text-rose-600 hover:bg-rose-50"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
