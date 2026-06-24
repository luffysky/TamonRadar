"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ThumbsUp, Flag } from "lucide-react";
import {
  getForumThread, createReply, deleteThread, deleteReply, likeThread, createReport,
  type ForumThread,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import RichContent from "@/components/social/RichContent";
import RichTextEditor from "@/components/social/RichTextEditor";

export default function ThreadView({ id }: { id: number }) {
  const { user } = useAuth();
  const toast = useToast();
  const router = useRouter();
  const [thread, setThread] = useState<ForumThread | null>(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState(false);
  const [liked, setLiked] = useState(false);

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
  async function like() {
    if (liked) return;
    try {
      const r = await likeThread(id);
      setThread((t) => (t ? { ...t, likes: r.likes } : t));
      setLiked(true);
    } catch { /* ignore */ }
  }
  async function report() {
    const reason = window.prompt("檢舉原因(會送到管理員處理佇列):");
    if (reason === null) return;
    try {
      await createReport("thread", id, reason);
      toast("已送出檢舉,感謝你的回報", "success");
    } catch {
      toast("檢舉失敗(需登入)", "error");
    }
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
        <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-700">
          <button onClick={like} className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition ${liked ? "border-brand-300 bg-brand-50 text-brand-600 dark:bg-brand-950/40" : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"}`}>
            <ThumbsUp className="h-4 w-4" /> 讚 {thread.likes ?? 0}
          </button>
          <button onClick={report} className="flex items-center gap-1.5 rounded-full border border-slate-300 px-3 py-1 text-sm text-slate-500 hover:bg-rose-50 hover:text-rose-600 dark:border-slate-600 dark:text-slate-400">
            <Flag className="h-4 w-4" /> 檢舉
          </button>
          {canManage(thread.author_id) && (
            <button onClick={removeThread} className="ml-auto text-xs text-rose-500 hover:underline">刪除主題</button>
          )}
        </div>
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
