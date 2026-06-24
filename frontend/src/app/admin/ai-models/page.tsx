"use client";

import { useEffect, useState } from "react";
import { useRequireAuth } from "@/components/AuthProvider";
import { getAiConfig, saveAiConfig, setAiDefault, testAiProvider, type AiConfig } from "@/lib/api";

const LABELS: Record<string, { name: string; placeholder: string; modelHint: string }> = {
  openai: { name: "OpenAI (GPT)", placeholder: "sk-...", modelHint: "gpt-4o-mini" },
  gemini: { name: "Google Gemini", placeholder: "AIza...", modelHint: "gemini-2.0-flash" },
  groq: { name: "Groq", placeholder: "gsk_...", modelHint: "llama-3.3-70b-versatile" },
  openrouter: { name: "OpenRouter", placeholder: "sk-or-...", modelHint: "openai/gpt-4o-mini" },
  anthropic: { name: "Anthropic (Claude)", placeholder: "sk-ant-...", modelHint: "claude-sonnet-4-6" },
};
const ORDER = ["openai", "gemini", "groq", "openrouter", "anthropic"];

export default function AdminAiModelsPage() {
  const { user, ready } = useRequireAuth();
  const [cfg, setCfg] = useState<AiConfig | null>(null);
  const [keyEdits, setKeyEdits] = useState<Record<string, string>>({});
  const [modelEdits, setModelEdits] = useState<Record<string, string>>({});
  const [test, setTest] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");

  async function load() { try { setCfg(await getAiConfig()); } catch { /* */ } }
  useEffect(() => { if (user) load(); }, [user]);

  if (!ready || !user) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  if (!user.is_admin) return <p className="py-20 text-center text-sm text-rose-500">沒有管理員權限。</p>;
  if (!cfg) return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;

  async function saveKey(p: string) {
    await saveAiConfig(p, { key: keyEdits[p] ?? "" });
    setKeyEdits((e) => ({ ...e, [p]: "" }));
    setMsg("✅ 已儲存金鑰"); load();
  }
  async function saveModel(p: string) {
    await saveAiConfig(p, { model: modelEdits[p] ?? "" });
    setMsg("✅ 已儲存模型"); load();
  }
  async function toggle(p: string, enabled: boolean) {
    await saveAiConfig(p, { enabled }); setMsg("✅ 已更新"); load();
  }
  async function makeDefault(p: string) { await setAiDefault(p); setMsg(`✅ 預設改為 ${p}`); load(); }
  async function runTest(p: string) {
    setTest((t) => ({ ...t, [p]: "測試中…" }));
    const r = await testAiProvider(p, keyEdits[p] || undefined);
    setTest((t) => ({ ...t, [p]: r.ok ? `✅ 可用 (${r.model})` : `❌ ${r.error || "失敗"}` }));
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">AI 模型 / 金鑰</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          在這裡集中設定各家 AI 金鑰與模型,Zeabur 不必再設 AI 環境變數。優先序:使用者自備 &gt; 這裡的設定 &gt; 環境變數。
        </p>
        <p className="mt-1 text-xs text-brand-600 dark:text-brand-300">目前預設 provider:{cfg.default_provider || "(自動,依有金鑰者)"}</p>
        {msg && <p className="mt-1 text-xs text-slate-500">{msg}</p>}
      </div>

      {ORDER.map((p) => {
        const c = cfg.providers[p];
        const l = LABELS[p];
        return (
          <div key={p} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold text-slate-700 dark:text-slate-200">{l.name}</h2>
              <span className={`rounded-full px-2 py-0.5 text-xs ${c.has_key ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400 dark:bg-slate-700"}`}>{c.has_key ? `✓ 已設定金鑰 ${c.key_hint || ""}` : "未設定金鑰"}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${c.enabled ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-400 dark:bg-slate-700"}`}>{c.enabled ? "啟用" : "停用"}</span>
              {cfg.default_provider === p && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">預設</span>}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input type="password" value={keyEdits[p] ?? ""} onChange={(e) => setKeyEdits((x) => ({ ...x, [p]: e.target.value }))}
                placeholder={c.has_key ? "輸入新金鑰以更換(留空儲存=清除)" : l.placeholder}
                className="min-w-[240px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900" />
              <button onClick={() => saveKey(p)} className="rounded-lg bg-brand-600 px-3 py-2 text-sm text-white hover:bg-brand-700">儲存金鑰</button>
              <button onClick={() => runTest(p)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">🧪 測試</button>
              {test[p] && <span className="text-xs text-slate-500">{test[p]}</span>}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input value={modelEdits[p] ?? c.model} onChange={(e) => setModelEdits((x) => ({ ...x, [p]: e.target.value }))}
                placeholder={`模型(預設 ${l.modelHint})`} className="min-w-[240px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900" />
              <button onClick={() => saveModel(p)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">儲存模型</button>
              <button onClick={() => toggle(p, !c.enabled)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">{c.enabled ? "停用" : "啟用"}</button>
              {cfg.default_provider !== p && <button onClick={() => makeDefault(p)} className="rounded-lg border border-amber-300 px-3 py-2 text-sm text-amber-600 hover:bg-amber-50">設為預設</button>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
