"use client";

import { useState } from "react";
import { ImagePlus, X } from "lucide-react";
import RichTextEditor from "@/components/social/RichTextEditor";
import { uploadFile, type BlogPost, type PostInput } from "@/lib/api";

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
  const [series, setSeries] = useState(initial?.series ?? "");
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));
  const [content, setContent] = useState(initial?.content ?? "");
  const [published, setPublished] = useState(initial?.published ?? false);
  const [password, setPassword] = useState((initial as { password?: string })?.password ?? "");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [aiTopic, setAiTopic] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  async function runAi(mode: "full" | "outline" | "refine") {
    setAiBusy(true); setMsg(null);
    try {
      const { aiWritePost } = await import("@/lib/api");
      const r = await aiWritePost(mode, aiTopic || title, content);
      if (mode === "refine") setContent(r.content);
      else setContent((content ? content + "\n\n" : "") + r.content);
      setMsg(`✅ AI 已${mode === "outline" ? "產生大綱" : mode === "refine" ? "潤飾" : "撰寫"}(${r.model})`);
    } catch (e) { setMsg(e instanceof Error ? e.message : "AI 產生失敗"); }
    finally { setAiBusy(false); }
  }

  async function runAiMeta() {
    setAiBusy(true); setMsg(null);
    try {
      const { aiMetaPost } = await import("@/lib/api");
      const r = await aiMetaPost(title, content);
      if (r.excerpt) setExcerpt(r.excerpt);
      if (r.tags?.length) setTags(r.tags.join(", "));
      setMsg("✅ AI 已產生摘要與標籤" + (r.seo_title ? `;建議標題:${r.seo_title}` : ""));
    } catch (e) { setMsg(e instanceof Error ? e.message : "AI SEO 失敗"); }
    finally { setAiBusy(false); }
  }
  async function runAiCover() {
    setAiBusy(true); setMsg(null);
    try {
      const { aiCoverPost } = await import("@/lib/api");
      const r = await aiCoverPost(title || aiTopic);
      setCover(r.url);
      setMsg("✅ AI 已生成封面");
    } catch (e) { setMsg(e instanceof Error ? e.message : "封面生成失敗"); }
    finally { setAiBusy(false); }
  }

  async function onCoverFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const r = await uploadFile(f);
      setCover(r.url);
    } catch {
      setMsg("封面上傳失敗");
    } finally {
      setUploading(false);
    }
  }

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900";

  async function submit(pub: boolean) {
    if (!title.trim()) { setMsg("請填標題"); return; }
    setBusy(true);
    setMsg(null);
    try {
      await onSubmit({
        title: title.trim(), slug: slug.trim(), excerpt: excerpt.trim(), content,
        cover_image: cover.trim(), category, series: series.trim(),
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        published: pub,
        password: password.trim(),
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
      <div>
        <span className="mb-1 block text-sm text-slate-600 dark:text-slate-300">封面圖(選填,直接上傳)</span>
        {cover ? (
          <div className="relative inline-block">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={cover} alt="封面" className="h-32 w-56 rounded-lg object-cover" />
            <button onClick={() => setCover("")} className="absolute right-1 top-1 grid h-6 w-6 place-items-center rounded-full bg-black/60 text-white"><X className="h-3.5 w-3.5" /></button>
          </div>
        ) : (
          <label className="flex h-32 w-56 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-slate-300 text-sm text-slate-400 hover:border-brand-400 dark:border-slate-600">
            <ImagePlus className="h-6 w-6" />
            {uploading ? "上傳中…" : "點擊上傳封面"}
            <input type="file" accept="image/*" onChange={onCoverFile} className="hidden" />
          </label>
        )}
      </div>
      <input value={series} onChange={(e) => setSeries(e.target.value)} placeholder="系列名稱(選填,同系列文章會歸在一起)" className={field} />
      <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="標籤(逗號分隔)" className={field} />
      <textarea value={excerpt} onChange={(e) => setExcerpt(e.target.value)} placeholder="摘要(選填)" rows={2} className={field} />

      <div className="rounded-lg border border-violet-200 bg-violet-50/50 p-3 dark:border-violet-900 dark:bg-violet-950/20">
        <p className="mb-2 text-sm font-medium text-violet-700 dark:text-violet-300">✨ AI 寫作助手</p>
        <div className="flex flex-wrap gap-2">
          <input value={aiTopic} onChange={(e) => setAiTopic(e.target.value)} placeholder="主題(留空用標題)" className={`${field} flex-1`} />
          <button onClick={() => runAi("full")} disabled={aiBusy} className="rounded-lg bg-violet-600 px-3 py-2 text-sm text-white hover:bg-violet-700 disabled:opacity-50">寫整篇</button>
          <button onClick={() => runAi("outline")} disabled={aiBusy} className="rounded-lg border border-violet-300 px-3 py-2 text-sm text-violet-700 hover:bg-violet-50 disabled:opacity-50">大綱</button>
          <button onClick={() => runAi("refine")} disabled={aiBusy || !content} className="rounded-lg border border-violet-300 px-3 py-2 text-sm text-violet-700 hover:bg-violet-50 disabled:opacity-50">潤飾現有</button>
          <button onClick={runAiMeta} disabled={aiBusy || !content} className="rounded-lg border border-violet-300 px-3 py-2 text-sm text-violet-700 hover:bg-violet-50 disabled:opacity-50">產 SEO/摘要</button>
          <button onClick={runAiCover} disabled={aiBusy || !(title || aiTopic)} className="rounded-lg border border-violet-300 px-3 py-2 text-sm text-violet-700 hover:bg-violet-50 disabled:opacity-50">生成封面</button>
        </div>
        {aiBusy && <p className="mt-1 text-xs text-violet-500">AI 處理中…</p>}
      </div>

      <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="🔒 文章密碼(選填,設了讀者要輸入密碼才能看內文)" className={field} />
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
