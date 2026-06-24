"use client";

import { useState } from "react";
import { askAssistant, type ChatTurn } from "@/lib/api";

export default function AssistantWidget() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([
    { role: "assistant", content: "嗨!我是 TamonRadar 小幫手,關於這個網站怎麼用都可以問我 😊" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    const next = [...turns, { role: "user" as const, content: q }];
    setTurns(next);
    setInput("");
    setLoading(true);
    try {
      const res = await askAssistant(q, next.slice(-8));
      setTurns([...next, { role: "assistant", content: res.answer }]);
    } catch {
      setTurns([...next, { role: "assistant", content: "抱歉,我暫時無法回答,請稍後再試。" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 left-4 z-40 grid h-12 w-12 place-items-center rounded-full bg-brand-600 text-xl text-white shadow-soft hover:bg-brand-700"
        aria-label="AI 助手"
      >
        {open ? "✕" : "💬"}
      </button>

      {open && (
        <div className="fixed bottom-20 left-4 z-40 flex h-[28rem] w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft dark:border-slate-700 dark:bg-slate-800">
          <div className="border-b border-slate-100 bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white dark:border-slate-700">
            📡 TamonRadar 小幫手
          </div>
          <div className="scroll-thin flex-1 space-y-3 overflow-auto p-3">
            {turns.map((t, i) => (
              <div key={i} className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                    t.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200"
                  }`}
                >
                  {t.content}
                </div>
              </div>
            ))}
            {loading && <div className="text-xs text-slate-400">小幫手思考中…</div>}
          </div>
          <div className="flex gap-2 border-t border-slate-100 p-2 dark:border-slate-700">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="問我這個網站怎麼用…"
              className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600"
            />
            <button onClick={send} disabled={loading} className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
              送出
            </button>
          </div>
        </div>
      )}
    </>
  );
}
