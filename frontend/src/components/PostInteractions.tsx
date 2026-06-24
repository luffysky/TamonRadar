"use client";

import { useState } from "react";
import { Heart, MessageCircle, Bookmark } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { likeBlogPost, addBlogComment, addFavorite, type BlogComment } from "@/lib/api";

export default function PostInteractions({
  postId, slug, title, coverImage, initialLikes, initialLiked, initialComments,
}: {
  postId: number; slug: string; title: string; coverImage?: string;
  initialLikes: number; initialLiked: boolean; initialComments: BlogComment[];
}) {
  const { user } = useAuth();
  const [likes, setLikes] = useState(initialLikes);
  const [liked, setLiked] = useState(initialLiked);
  const [comments, setComments] = useState<BlogComment[]>(initialComments);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [faved, setFaved] = useState(false);
  const [msg, setMsg] = useState("");

  async function like() {
    if (!user) { setMsg("請先登入"); return; }
    try { const r = await likeBlogPost(postId); setLiked(r.liked); setLikes(r.likes); } catch { /* */ }
  }
  async function fav() {
    if (!user) { setMsg("請先登入"); return; }
    try { await addFavorite({ url: `/blog/${slug}`, title, image_url: coverImage || "" }); setFaved(true); setMsg("已加入收藏"); } catch { setMsg("收藏失敗"); }
  }
  async function submit() {
    if (!user) { setMsg("請先登入才能留言"); return; }
    const c = text.trim();
    if (!c) return;
    setBusy(true);
    try { const nc = await addBlogComment(postId, c); setComments([nc, ...comments]); setText(""); }
    catch { setMsg("留言失敗"); }
    finally { setBusy(false); }
  }

  return (
    <div className="mt-8 border-t border-slate-200 pt-6 dark:border-slate-700">
      <div className="flex items-center gap-3">
        <button onClick={like} className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm transition ${liked ? "border-rose-300 bg-rose-50 text-rose-600 dark:bg-rose-950" : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300"}`}>
          <Heart className={`h-4 w-4 ${liked ? "fill-rose-500 text-rose-500" : ""}`} /> {likes}
        </button>
        <button onClick={fav} className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm transition ${faved ? "border-brand-300 bg-brand-50 text-brand-600 dark:bg-brand-950" : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300"}`}>
          <Bookmark className={`h-4 w-4 ${faved ? "fill-brand-500 text-brand-500" : ""}`} /> 收藏
        </button>
        <span className="flex items-center gap-1.5 text-sm text-slate-400"><MessageCircle className="h-4 w-4" /> {comments.length}</span>
        {msg && <span className="text-xs text-slate-400">{msg}</span>}
      </div>

      <div className="mt-6">
        <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">留言 ({comments.length})</h3>
        {user ? (
          <div className="mb-4 flex gap-2">
            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="寫下你的留言…" className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900" />
            <button onClick={submit} disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">送出</button>
          </div>
        ) : (
          <p className="mb-4 text-sm text-slate-400">登入後即可留言。</p>
        )}
        <div className="space-y-3">
          {comments.length === 0 ? <p className="text-sm text-slate-400">還沒有留言,當第一個吧!</p> : comments.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-100 p-3 text-sm dark:border-slate-700">
              <p className="text-xs text-slate-400">{c.author_name} · {c.created_at ? new Date(c.created_at).toLocaleString("zh-TW") : ""}</p>
              <p className="mt-1 whitespace-pre-wrap text-slate-700 dark:text-slate-200">{c.content}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
