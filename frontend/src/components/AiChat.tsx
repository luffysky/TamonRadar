"use client";

import { useState } from "react";
import { MessagesSquare, Send } from "lucide-react";
import { aiChat } from "@/lib/api";

const SUGGESTIONS = ["幫我整理這次搜尋的重點", "最重要的幾個來源是哪些?", "有哪些值得注意的項目?"];

export default function AiChat({ runId }: { runId: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask(q?: string) {
    const query = (q ?? question).trim();
    if (!query) return;
    setQuestion(query);
    setLoading(true);
    setAnswer(null);
    try {
      const res = await aiChat(runId, query);
      setAnswer(res.answer);
    } catch {
      setAnswer("發生錯誤,請稍後再試。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="mb-3 flex items-center gap-2">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-violet-100 text-violet-600 dark:bg-violet-950 dark:text-violet-300">
          <MessagesSquare className="h-4 w-4" />
        </div>
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">問 AI(對這批資料提問)</h3>
      </div>

      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="例如:最便宜的是哪個?"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none dark:border-slate-600"
        />
        <button
          onClick={() => ask()}
          disabled={loading}
          className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-violet-600 text-white transition hover:bg-violet-700 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300"
          >
            {s}
          </button>
        ))}
      </div>

      {loading && <p className="mt-3 text-sm text-slate-400">思考中…</p>}
      {answer && (
        <div className="mt-3 whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-sm leading-relaxed text-slate-700 dark:bg-slate-900/50 dark:text-slate-200">
          {answer}
        </div>
      )}
    </div>
  );
}
