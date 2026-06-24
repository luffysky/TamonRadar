"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { summarize } from "@/lib/api";

export default function AiSummary({ runId }: { runId: string }) {
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await summarize(runId);
      setText(res.summary);
    } catch {
      setError("AI 摘要產生失敗,請確認後端與 API key。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-violet-200 bg-violet-50/60 p-4 shadow-sm dark:border-violet-900 dark:bg-violet-950/30">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-violet-700"><Sparkles className="h-4 w-4" /> AI 情報摘要</h3>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? "分析中…" : text ? "重新分析" : "用 AI 分析這批資料"}
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      {text && (
        <div className="prose-sm mt-3 whitespace-pre-wrap rounded-lg bg-white dark:bg-slate-800 p-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
          {text}
        </div>
      )}
      {!text && !error && (
        <p className="mt-2 text-xs text-violet-500/80">
          會用 AI(預設 GPT)針對你搜尋的主題,從結果中抓出重點、整理重要資訊、標出可能的雜訊。
        </p>
      )}
    </div>
  );
}
