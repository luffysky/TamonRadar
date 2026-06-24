"use client";

import { useEffect, useState } from "react";
import { Heart, Bookmark, ThumbsUp, CornerDownRight } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import {
  likeBlogPost, addBlogComment, addFavorite, likeComment, getReactions, toggleReaction,
  incrementView, type BlogComment,
} from "@/lib/api";

const EMOJIS = ["❤️", "🔥", "👏", "😮", "😂", "🎉"];

function CommentNode({ c, onReply, onLike, depth = 0 }: { c: BlogComment; onReply: (id: number, name: string) => void; onLike: (id: number) => void; depth?: number }) {
  return (
    <div className={depth > 0 ? "ml-6 border-l border-slate-100 pl-3 dark:border-slate-700" : ""}>
      <div className="rounded-lg border border-slate-100 p-3 text-sm dark:border-slate-700">
        <p className="text-xs text-slate-400">{c.author_name} · {c.created_at ? new Date(c.created_at).toLocaleString("zh-TW") : ""}</p>
        <p className="mt-1 whitespace-pre-wrap text-slate-700 dark:text-slate-200">{c.content}</p>
        <div className="mt-1.5 flex items-center gap-3 text-xs">
          <button onClick={() => onLike(c.id)} className="flex items-center gap-1 text-slate-400 hover:text-rose-500"><ThumbsUp className="h-3.5 w-3.5" /> {c.like_count || 0}</button>
          {depth === 0 && <button onClick={() => onReply(c.id, c.author_name)} className="flex items-center gap-1 text-slate-400 hover:text-brand-500"><CornerDownRight className="h-3.5 w-3.5" /> 回覆</button>}
        </div>
      </div>
      {c.replies && c.replies.map((r) => <div key={r.id} className="mt-2"><CommentNode c={r} onReply={onReply} onLike={onLike} depth={depth + 1} /></div>)}
    </div>
  );
}

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
  const [replyTo, setReplyTo] = useState<{ id: number; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [faved, setFaved] = useState(false);
  const [msg, setMsg] = useState("");
  const [reactions, setReactions] = useState<{ counts: Record<string, number>; mine: string[] }>({ counts: {}, mine: [] });

  useEffect(() => { incrementView(postId); getReactions(postId).then(setReactions).catch(() => {}); }, [postId]);

  function countComments(list: BlogComment[]): number {
    return list.reduce((n, c) => n + 1 + (c.replies ? countComments(c.replies) : 0), 0);
  }
  async function like() {
    if (!user) return setMsg("請先登入");
    try { const r = await likeBlogPost(postId); setLiked(r.liked); setLikes(r.likes); } catch { /* */ }
  }
  async function react(emoji: string) {
    if (!user) return setMsg("請先登入");
    try { setReactions(await toggleReaction(postId, emoji)); } catch { /* */ }
  }
  async function fav() {
    if (!user) return setMsg("請先登入");
    try { await addFavorite({ url: `/blog/${slug}`, title, image_url: coverImage || "" }); setFaved(true); setMsg("已加入收藏"); } catch { setMsg("收藏失敗"); }
  }
  async function likeC(id: number) {
    if (!user) return setMsg("請先登入");
    try {
      const r = await likeComment(id);
      setComments((cs) => cs.map(function upd(c): BlogComment {
        if (c.id === id) return { ...c, like_count: r.like_count };
        return { ...c, replies: c.replies?.map(upd) };
      }));
    } catch { /* */ }
  }
  async function submit() {
    if (!user) return setMsg("請先登入才能留言");
    const c = text.trim(); if (!c) return;
    setBusy(true);
    try {
      const nc = await addBlogComment(postId, c, replyTo?.id);
      if (replyTo) {
        setComments((cs) => cs.map((x) => x.id === replyTo.id ? { ...x, replies: [...(x.replies || []), nc] } : x));
      } else {
        setComments((cs) => [nc, ...cs]);
      }
      setText(""); setReplyTo(null);
    } catch { setMsg("留言失敗"); } finally { setBusy(false); }
  }

  return (
    <div className="mt-8 border-t border-slate-200 pt-6 dark:border-slate-700">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={like} className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm transition ${liked ? "border-rose-300 bg-rose-50 text-rose-600 dark:bg-rose-950" : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300"}`}>
          <Heart className={`h-4 w-4 ${liked ? "fill-rose-500 text-rose-500" : ""}`} /> {likes}
        </button>
        <button onClick={fav} className={`flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm transition ${faved ? "border-brand-300 bg-brand-50 text-brand-600 dark:bg-brand-950" : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300"}`}>
          <Bookmark className={`h-4 w-4 ${faved ? "fill-brand-500 text-brand-500" : ""}`} /> 收藏
        </button>
        {msg && <span className="text-xs text-slate-400">{msg}</span>}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {EMOJIS.map((e) => {
          const on = reactions.mine.includes(e);
          return (
            <button key={e} onClick={() => react(e)} className={`rounded-full border px-2.5 py-1 text-sm transition ${on ? "border-brand-300 bg-brand-50 dark:bg-brand-950" : "border-slate-200 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700"}`}>
              {e} {reactions.counts[e] ? <span className="text-xs text-slate-500">{reactions.counts[e]}</span> : null}
            </button>
          );
        })}
      </div>

      <div className="mt-6">
        <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">留言 ({countComments(comments)})</h3>
        {user ? (
          <div className="mb-4">
            {replyTo && <p className="mb-1 text-xs text-brand-600">回覆 @{replyTo.name} <button onClick={() => setReplyTo(null)} className="text-slate-400">✕取消</button></p>}
            <div className="flex gap-2">
              <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder={replyTo ? "寫下回覆…" : "寫下你的留言…"} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900" />
              <button onClick={submit} disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">送出</button>
            </div>
          </div>
        ) : <p className="mb-4 text-sm text-slate-400">登入後即可留言。</p>}
        <div className="space-y-3">
          {comments.length === 0 ? <p className="text-sm text-slate-400">還沒有留言,當第一個吧!</p> :
            comments.map((c) => <CommentNode key={c.id} c={c} onReply={(id, name) => { setReplyTo({ id, name }); }} onLike={likeC} />)}
        </div>
      </div>
    </div>
  );
}
