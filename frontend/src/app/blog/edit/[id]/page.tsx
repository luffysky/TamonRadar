"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/components/AuthProvider";
import PostEditor from "@/components/PostEditor";
import { getMyPost, myUpdatePost, getPreviewToken, type BlogPost } from "@/lib/api";

export default function EditPostPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const { user, ready } = useRequireAuth();
  const router = useRouter();
  const [post, setPost] = useState<BlogPost | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    getMyPost(id).then(setPost).catch((e) => setErr(e instanceof Error ? e.message : "讀取失敗"));
  }, [user, id]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (err) return <p className="py-20 text-center text-sm text-rose-500">{err}</p>;
  if (!post) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">編輯文章</h1>
        <button
          onClick={async () => { try { const { token } = await getPreviewToken(id); window.open(`/blog/preview/${token}`, "_blank"); } catch { /* */ } }}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"
        >👁 預覽草稿</button>
      </div>
      <PostEditor initial={post} onSubmit={async (d) => { await myUpdatePost(id, d); router.push("/blog/mine"); }} />
    </div>
  );
}
