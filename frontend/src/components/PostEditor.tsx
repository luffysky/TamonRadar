"use client";

import { useState } from "react";
import RichTextEditor from "@/components/social/RichTextEditor";
import type { BlogPost, PostInput } from "@/lib/api";

const CATEGORIES = ["旅遊", "攝影", "烹飪", "動漫", "周邊", "演唱會", "開箱", "心得", "其他"];

export default function PostEditor({
  initial,
  onSubmit,
}: {
  initial?: BlogPost;
  onSubmit: (data: PostInput) => Promise<void>;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [excerpt, setExcerpt] = useState(initial?.excerpt ?? "");
  const [cover, setCover] = useState(initial?.cover_image ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));
  const [content, setContent] = useState(initial?.content ?? "");
  const [published, setPublished] = useState(initial?.published ?? false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900";

  async function submit(pub: boolean) {
    if (!title.trim()) { setMsg("請填標題"); return; }
    setBusy(true);
    setMsg(null);
    try {
      await onSubmit({
        title: title.trim(), slug: slug.trim(), excerpt: excerpt.trim(), content,
        cover_image: cover.trim(), category, tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        published: pub,
      });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "儲存失敗");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="標題" className={`${field} text-lg font-semibold`} />
      <div className="grid gap-3 sm:grid-cols-2">
        <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="網址代稱(slug,可留空自動產生)" className={field} />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={field}>
          <option value="">選分類</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <input value={cover} onChange={(e) => setCover(e.target.value)} placeholder="封面圖網址(選填)" className={field} />
      <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="標籤(逗號分隔)" className={field} />
      <textarea value={excerpt} onChange={(e) => setExcerpt(e.target.value)} placeholder="摘要(選填)" rows={2} className={field} />
      <RichTextEditor content={content} onChange={setContent} />

      <div className="flex flex-wrap items-center gap-3">
        <button onClick={() => submit(true)} disabled={busy} className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
          {busy ? "儲存中…" : "發佈"}
        </button>
        <button onClick={() => submit(false)} disabled={busy} className="rounded-lg border border-slate-300 px-5 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">
          存為草稿
        </button>
        <label className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
          <input type="checkbox" checked={published} onChange={(e) => setPublished(e.target.checked)} disabled /> {initial?.published ? "目前:已發佈" : "目前:草稿"}
        </label>
        {msg && <span className="text-sm text-rose-500">{msg}</span>}
      </div>
    </div>
  );
}
