"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, Sparkles } from "lucide-react";
import { askAssistant, type ChatTurn } from "@/lib/api";

export default function AssistantWidget() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([
    { role: "assistant", content: "嗨!我是 TamonRadar 小幫手,關於這個網站怎麼用都可以問我。" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading, open]);

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
        data-tour="assistant"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 left-5 z-40 grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-lg shadow-brand-600/30 transition hover:scale-105 active:scale-95"
        aria-label="AI 助手"
      >
        {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>

      {open && (
        <div className="animate-slide-up fixed bottom-24 left-5 z-40 flex h-[30rem] w-[min(23rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-800">
          {/* header */}
          <div className="flex items-center gap-3 bg-gradient-to-r from-brand-600 to-brand-500 px-4 py-3 text-white">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-white/20">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">TamonRadar 小幫手</div>
              <div className="text-[11px] text-white/70">線上 · 隨時問我</div>
            </div>
            <button onClick={() => setOpen(false)} className="ml-auto rounded-full p-1 hover:bg-white/15">
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* messages */}
          <div className="scroll-thin flex-1 space-y-3 overflow-auto bg-slate-50 p-3 dark:bg-slate-900/40">
            {turns.map((t, i) =>
              t.role === "assistant" ? (
                <div key={i} className="flex items-end gap-2">
                  <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-100 text-brand-600 dark:bg-slate-700 dark:text-brand-300">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-white px-3.5 py-2 text-sm text-slate-700 shadow-sm dark:bg-slate-700 dark:text-slate-100">
                    {t.content}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-sm text-white shadow-sm">
                    {t.content}
                  </div>
                </div>
              )
            )}
            {loading && (
              <div className="flex items-end gap-2">
                <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-100 text-brand-600 dark:bg-slate-700 dark:text-brand-300">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-white px-4 py-3 shadow-sm dark:bg-slate-700">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* input */}
          <div className="flex items-center gap-2 border-t border-slate-100 bg-white p-2.5 dark:border-slate-700 dark:bg-slate-800">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="輸入訊息…"
              className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600"
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-600 text-white transition hover:bg-brand-700 disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
