"use client";

import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/components/AuthProvider";
import PostEditor from "@/components/PostEditor";
import { myCreatePost } from "@/lib/api";

export default function NewPostPage() {
  const { user, ready } = useRequireAuth();
  const router = useRouter();
  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">寫文章</h1>
      <PostEditor onSubmit={async (d) => { await myCreatePost(d); router.push("/blog/mine"); }} />
    </div>
  );
}
