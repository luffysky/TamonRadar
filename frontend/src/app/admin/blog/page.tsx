"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  adminListPosts, adminGetPost, createPost, updatePost, deletePost,
  type BlogPost, type PostInput,
} from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import RichTextEditor from "@/components/social/RichTextEditor";

const EMPTY: PostInput = {
  title: "", slug: "", excerpt: "", content: "", cover_image: "", category: "", tags: [], published: false,
};

export default function AdminBlogPage() {
  const { user, ready } = useRequireAuth();
  const toast = useToast();
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [form, setForm] = useState<PostInput>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setPosts((await adminListPosts()).posts);
    } catch {
      /* ignore */
    }
  }
  useEffect(() => { if (user) load(); }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;

  function reset() { setForm(EMPTY); setEditingId(null); }

  async function edit(id: number) {
    const p = await adminGetPost(id);
    setEditingId(id);
    setForm({
      title: p.title, slug: p.slug, excerpt: p.excerpt, content: p.content ?? "",
      cover_image: p.cover_image, category: p.category, tags: p.tags, published: p.published,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function save() {
    if (!form.title.trim()) { toast("請輸入標題", "error"); return; }
    setSaving(true);
    try {
      if (editingId) { await updatePost(editingId, form); toast("已更新", "success"); }
      else { await createPost(form); toast("已建立", "success"); }
      reset();
      load();
    } catch {
      toast("儲存失敗", "error");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    await deletePost(id);
    if (editingId === id) reset();
    load();
    toast("已刪除", "info");
  }

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">部落格管理</h1>
        <Link href="/admin" className="text-sm text-brand-600 hover:underline dark:text-brand-300">← 回管理後台</Link>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{editingId ? `編輯文章 #${editingId}` : "新增文章"}</p>
        <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="標題" className={field} />
        <div className="grid gap-3 sm:grid-cols-2">
          <input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="網址 slug(留空自動產生)" className={field} />
          <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="分類(例:攻略)" className={field} />
        </div>
        <input value={form.cover_image} onChange={(e) => setForm({ ...form, cover_image: e.target.value })} placeholder="封面圖網址(選填)" className={field} />
        <input value={form.excerpt} onChange={(e) => setForm({ ...form, excerpt: e.target.value })} placeholder="摘要(列表/SEO 用)" className={field} />
        <RichTextEditor content={form.content} onChange={(html) => setForm({ ...form, content: html })} placeholder="內文…" />
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={form.published} onChange={(e) => setForm({ ...form, published: e.target.checked })} />
          發布(打勾才會公開顯示)
        </label>
        <div className="flex gap-2">
          <button onClick={save} disabled={saving} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            {editingId ? "更新" : "建立"}
          </button>
          {editingId && <button onClick={reset} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">取消編輯</button>}
        </div>
      </div>

      <div className="space-y-2">
        {posts.map((p) => (
          <div key={p.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{p.title}</p>
              <p className="text-xs text-slate-400">/{p.slug} · {p.category || "未分類"}</p>
            </div>
            <span className={`rounded-full px-2 py-0.5 text-xs ${p.published ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"}`}>
              {p.published ? "已發布" : "草稿"}
            </span>
            <button onClick={() => edit(p.id)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">編輯</button>
            <button onClick={() => remove(p.id)} className="rounded-md border border-rose-200 px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50">刪除</button>
          </div>
        ))}
      </div>
    </div>
  );
}
