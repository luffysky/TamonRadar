"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getForumThread, createReply, deleteThread, deleteReply,
  type ForumThread,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import RichContent from "@/components/social/RichContent";
import RichTextEditor from "@/components/social/RichTextEditor";

export default function ThreadPage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const { user } = useAuth();
  const toast = useToast();
  const router = useRouter();
  const [thread, setThread] = useState<ForumThread | null>(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState(false);

  async function load() {
    try {
      setThread(await getForumThread(id));
    } catch {
      setError(true);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (error) return <p className="py-20 text-center text-sm text-rose-500">找不到這個主題。</p>;
  if (!thread) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  const canManage = (authorId: number) => user && (user.id === authorId || user.is_admin);

  async function submitReply() {
    if (!reply.trim()) return;
    try {
      await createReply(id, reply.trim());
      setReply("");
      load();
    } catch {
      toast("回覆失敗", "error");
    }
  }

  async function removeThread() {
    await deleteThread(id);
    toast("已刪除主題", "info");
    router.push(`/forum/${thread!.category}`);
  }

  async function removeReply(rid: number) {
    await deleteReply(rid);
    load();
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link href={`/forum/${thread.category}`} className="text-sm text-brand-600 hover:underline dark:text-brand-300">← 回分類</Link>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">{thread.title}</h1>
        <p className="mt-1 text-xs text-slate-400">
          {thread.author} · {thread.created_at ? new Date(thread.created_at).toLocaleString("zh-TW") : ""}
        </p>
        <div className="mt-3"><RichContent html={thread.content ?? ""} /></div>
        {canManage(thread.author_id) && (
          <button onClick={removeThread} className="mt-3 text-xs text-rose-500 hover:underline">刪除主題</button>
        )}
      </div>

      <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">{thread.replies?.length ?? 0} 則回覆</h2>
      <div className="space-y-2">
        {thread.replies?.map((r) => (
          <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <p className="text-xs text-slate-400">{r.author} · {r.created_at ? new Date(r.created_at).toLocaleString("zh-TW") : ""}</p>
            <div className="mt-1"><RichContent html={r.content} /></div>
            {canManage(r.author_id) && (
              <button onClick={() => removeReply(r.id)} className="mt-1 text-xs text-rose-500 hover:underline">刪除</button>
            )}
          </div>
        ))}
      </div>

      {user ? (
        <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <RichTextEditor content={reply} onChange={setReply} placeholder="回覆…" />
          <button onClick={submitReply} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">送出回覆</button>
        </div>
      ) : (
        <Link href="/login" className="inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">登入後回覆</Link>
      )}
    </div>
  );
}
