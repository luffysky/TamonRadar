"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { API_BASE, type BlogPost } from "@/lib/api";
import RichContent from "@/components/social/RichContent";

export default function PreviewPage({ params: paramsPromise }: { params: Promise<{ token: string }> }) {
  const params = use(paramsPromise);
  const [post, setPost] = useState<BlogPost | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/blog/preview/${params.token}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPost)
      .catch(() => setErr("預覽連結無效或已失效"));
  }, [params.token]);

  if (err) return <p className="py-20 text-center text-sm text-rose-500">{err}</p>;
  if (!post) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  return (
    <article className="mx-auto max-w-3xl">
      <div className="mb-3 rounded-lg bg-amber-100 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
        👁 草稿預覽模式{post.published ? "" : "(此文章尚未發佈,只有持此連結者看得到)"}
      </div>
      <Link href="/blog" className="text-sm text-brand-600 hover:underline dark:text-brand-300">← 回部落格</Link>
      <h1 className="mt-2 text-3xl font-bold text-slate-800 dark:text-slate-100">{post.title}</h1>
      {post.cover_image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.cover_image} alt={post.title} className="mt-4 w-full rounded-xl object-cover" />
      )}
      <div className="mt-6"><RichContent html={post.content ?? ""} /></div>
    </article>
  );
}
