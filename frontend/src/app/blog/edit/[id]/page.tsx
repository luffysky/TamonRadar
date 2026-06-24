"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/components/AuthProvider";
import PostEditor from "@/components/PostEditor";
import { getMyPost, myUpdatePost, type BlogPost } from "@/lib/api";

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
      <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">編輯文章</h1>
      <PostEditor initial={post} onSubmit={async (d) => { await myUpdatePost(id, d); router.push("/blog/mine"); }} />
    </div>
  );
}
