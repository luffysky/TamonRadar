"use client";

import { useState } from "react";
import { aiChat } from "@/lib/api";

const SUGGESTIONS = ["最便宜的壓克力立牌是哪個?", "有哪些福原多聞的周邊?", "幫我整理值得買的前五名"];

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
    <div className="rounded-2xl border border-violet-200 bg-violet-50/60 p-4 shadow-sm dark:border-violet-900 dark:bg-violet-950/30">
      <h3 className="mb-2 text-sm font-semibold text-violet-700">💬 問 AI(對這批資料提問)</h3>
      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="例如:最便宜的櫻利夏立牌是哪個?"
          className="flex-1 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none"
        />
        <button
          onClick={() => ask()}
          disabled={loading}
          className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? "思考中…" : "問"}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            className="rounded-full border border-violet-200 bg-white dark:bg-slate-800 px-2.5 py-1 text-xs text-violet-600 hover:bg-violet-100"
          >
            {s}
          </button>
        ))}
      </div>
      {answer && (
        <div className="mt-3 whitespace-pre-wrap rounded-lg bg-white dark:bg-slate-800 p-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
          {answer}
        </div>
      )}
    </div>
  );
}
