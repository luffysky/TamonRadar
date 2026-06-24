"use client";

import { useEffect, useState } from "react";
import { getSettings, saveSettings, testNotify, changePassword, deleteAccount, updateProfile, type NotifySettings } from "@/lib/api";
import { useRequireAuth, useAuth } from "@/components/AuthProvider";
import PasswordInput from "@/components/PasswordInput";
import PushToggle from "@/components/PushToggle";

export default function SettingsPage() {
  const { user, ready } = useRequireAuth();
  const { signOut } = useAuth();
  const [uname, setUname] = useState("");
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMsg, setPwMsg] = useState<string | null>(null);
  const [form, setForm] = useState<NotifySettings>({
    discord_webhook: "", discord_user_id: "", telegram_token: "", telegram_chat_id: "",
    openai_key: "", anthropic_key: "", gemini_key: "", groq_key: "", openrouter_key: "", ai_provider: "",
    daily_digest: false,
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    getSettings().then(setForm).catch(() => {});
    setUname(user.username || "");
  }, [user]);

  if (!ready || !user) {
    return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  }

  async function save() {
    setSaving(true); setMsg(null);
    try {
      await saveSettings(form);
      setMsg("✅ 已儲存");
    } catch {
      setMsg("❌ 儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  async function test() {
    setMsg("測試發送中…");
    try {
      await saveSettings(form);
      const res = await testNotify();
      const ok = Object.values(res.results).some((r) => r.ok);
      setMsg(ok ? "✅ 測試通知已送出,去看看你的 Discord / Telegram" : "❌ 發送失敗,請檢查設定");
    } catch (e) {
      setMsg("❌ " + (e instanceof Error ? e.message : "測試失敗"));
    }
  }

  const field = "w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">通知設定</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">設定後,排程爬蟲跑完有新品/降價就會推播給你。</p>

      <div className="space-y-5 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Discord Webhook</label>
          <input
            value={form.discord_webhook}
            onChange={(e) => setForm({ ...form, discord_webhook: e.target.value })}
            placeholder="https://discord.com/api/webhooks/..."
            className={field}
          />
          <p className="mt-1 text-xs text-slate-400">
            Discord 頻道 → 編輯頻道 → 整合 → Webhook → 複製 Webhook 網址
          </p>
          <label className="mb-1 mt-3 block text-sm font-medium text-slate-700 dark:text-slate-200">或:Discord 使用者 ID(用平台 bot 私訊你)</label>
          <input
            value={form.discord_user_id}
            onChange={(e) => setForm({ ...form, discord_user_id: e.target.value })}
            placeholder="你的 Discord 使用者 ID(開發者模式→右鍵你的頭像→複製 ID)"
            className={field}
          />
          <p className="mt-1 text-xs text-slate-400">
            不想自己建 webhook 就填這個 → 由平台共用 bot 私訊你(需與 bot 同伺服器或允許陌生 DM)。
          </p>
        </div>

        <div className="border-t border-slate-100 dark:border-slate-700 pt-4">
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Telegram Chat ID(必填)</label>
          <input
            value={form.telegram_chat_id}
            onChange={(e) => setForm({ ...form, telegram_chat_id: e.target.value })}
            placeholder="你的 chat id(向 @userinfobot 詢問)"
            className={field}
          />
          <label className="mb-1 mt-3 block text-sm font-medium text-slate-700 dark:text-slate-200">Telegram Bot Token(選填)</label>
          <input
            value={form.telegram_token}
            onChange={(e) => setForm({ ...form, telegram_token: e.target.value })}
            placeholder="留空 = 用平台共用 bot 發送"
            className={field}
          />
          <p className="mt-1 text-xs text-slate-400">
            最簡單:**只填 Chat ID**,先到平台的 Telegram bot 按一次「開始」,通知就由共用 bot 發給你;要用自己的 bot 才填 token。
          </p>
        </div>

        <div className="border-t border-slate-100 pt-4 dark:border-slate-700">
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">AI 金鑰(自備,選用)</label>
          <p className="mb-2 text-xs text-slate-400">
            填自己的金鑰,AI 摘要/對話/濾雜訊就用你的額度(各付各的);留空則用網站提供的。
          </p>
          <input
            type="password" value={form.openai_key}
            onChange={(e) => setForm({ ...form, openai_key: e.target.value })}
            placeholder="OpenAI API Key(sk-...)" className={field}
          />
          <input
            type="password" value={form.anthropic_key}
            onChange={(e) => setForm({ ...form, anthropic_key: e.target.value })}
            placeholder="Anthropic API Key(sk-ant-...)" className={`${field} mt-2`}
          />
          <input
            type="password" value={form.gemini_key}
            onChange={(e) => setForm({ ...form, gemini_key: e.target.value })}
            placeholder="Google Gemini API Key" className={`${field} mt-2`}
          />
          <input
            type="password" value={form.groq_key}
            onChange={(e) => setForm({ ...form, groq_key: e.target.value })}
            placeholder="Groq API Key(gsk_...)" className={`${field} mt-2`}
          />
          <input
            type="password" value={form.openrouter_key}
            onChange={(e) => setForm({ ...form, openrouter_key: e.target.value })}
            placeholder="OpenRouter API Key(sk-or-...)" className={`${field} mt-2`}
          />
          <select
            value={form.ai_provider}
            onChange={(e) => setForm({ ...form, ai_provider: e.target.value })}
            className={`${field} mt-2`}
          >
            <option value="">自動(依有填的金鑰)</option>
            <option value="openai">優先 OpenAI(GPT)</option>
            <option value="gemini">優先 Gemini</option>
            <option value="groq">優先 Groq</option>
            <option value="openrouter">優先 OpenRouter</option>
            <option value="anthropic">優先 Claude</option>
          </select>
        </div>

        <label className="flex items-center gap-2 border-t border-slate-100 pt-3 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300">
          <input type="checkbox" checked={form.daily_digest} onChange={(e) => setForm({ ...form, daily_digest: e.target.checked })} />
          每日彙整通知(每天一封總結,而非每次變化都推)
        </label>

        <div className="border-t border-slate-100 pt-3 dark:border-slate-700">
          <p className="mb-1.5 text-sm font-medium text-slate-700 dark:text-slate-200">瀏覽器系統通知</p>
          <p className="mb-2 text-xs text-slate-400">不用 Discord/Telegram,關著網站也能在桌面/手機收到系統通知。</p>
          <PushToggle />
        </div>

        <div className="flex items-center gap-3">
          <button onClick={save} disabled={saving} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            儲存
          </button>
          <button onClick={test} className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm hover:bg-slate-50 dark:bg-slate-900">
            儲存並測試發送
          </button>
          {msg && <span className="text-sm text-slate-500 dark:text-slate-400">{msg}</span>}
        </div>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="font-semibold text-slate-700 dark:text-slate-200">帳號</h2>
        <p className="text-xs text-slate-400">{user.email}{user.is_admin ? " · 管理員" : ""}{user.privileged ? " · 特權" : ""}</p>

        <label className="block pt-2 text-sm font-medium text-slate-700 dark:text-slate-200">顯示名稱</label>
        <div className="flex gap-2">
          <input value={uname} onChange={(e) => setUname(e.target.value)} placeholder="你的名稱" className={field} />
          <button
            onClick={async () => { try { await updateProfile(uname); setPwMsg("✅ 名稱已更新(重新整理後生效)"); } catch { setPwMsg("❌ 更新失敗"); } }}
            className="shrink-0 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >更新</button>
        </div>

        <label className="block pt-2 text-sm font-medium text-slate-700 dark:text-slate-200">變更密碼</label>
        <PasswordInput value={curPw} onChange={setCurPw} placeholder="目前密碼" className={field} autoComplete="current-password" />
        <div className="mt-2"><PasswordInput value={newPw} onChange={setNewPw} placeholder="新密碼(至少 6 字)" className={field} autoComplete="new-password" /></div>
        <div className="flex items-center gap-3">
          <button
            onClick={async () => {
              try { await changePassword(curPw, newPw); setPwMsg("✅ 密碼已更新"); setCurPw(""); setNewPw(""); }
              catch (e) { setPwMsg("❌ " + (e instanceof Error ? e.message : "失敗")); }
            }}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            更新密碼
          </button>
          {pwMsg && <span className="text-sm text-slate-500 dark:text-slate-400">{pwMsg}</span>}
        </div>

        <div className="border-t border-slate-100 pt-3 dark:border-slate-700">
          <button
            onClick={async () => {
              if (!confirm("確定要刪除帳號?你的所有資料(搜尋/收藏/監看/排程/發文)會永久刪除,無法復原。")) return;
              try { await deleteAccount(); signOut(); } catch { alert("刪除失敗,請稍後再試"); }
            }}
            className="rounded-lg border border-rose-300 px-4 py-2 text-sm text-rose-600 hover:bg-rose-50"
          >
            刪除帳號
          </button>
        </div>
      </div>
    </div>
  );
}
