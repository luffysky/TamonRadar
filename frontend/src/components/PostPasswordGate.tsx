"use client";

import { useState } from "react";
import { Lock } from "lucide-react";
import { unlockPost } from "@/lib/api";
import RichContent from "@/components/social/RichContent";

export default function PostPasswordGate({ postId }: { postId: number }) {
  const [pw, setPw] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState("");

  async function submit() {
    setErr("");
    try { const r = await unlockPost(postId, pw); setHtml(r.content); }
    catch { setErr("密碼錯誤"); }
  }

  if (html !== null) return <div className="mt-6"><RichContent html={html} /></div>;

  return (
    <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-8 text-center dark:border-slate-700 dark:bg-slate-800/50">
      <Lock className="mx-auto h-8 w-8 text-slate-400" />
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">這是密碼保護的文章,請輸入密碼閱讀。</p>
      <div className="mx-auto mt-4 flex max-w-xs gap-2">
        <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="密碼" className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900" />
        <button onClick={submit} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">解鎖</button>
      </div>
      {err && <p className="mt-2 text-xs text-rose-500">{err}</p>}
    </div>
  );
}
