"use client";

import { useEffect, useState } from "react";
import { getSettings, saveSettings, testNotify, type NotifySettings } from "@/lib/api";
import { useRequireAuth } from "@/components/AuthProvider";

export default function SettingsPage() {
  const { user, ready } = useRequireAuth();
  const [form, setForm] = useState<NotifySettings>({
    discord_webhook: "", telegram_token: "", telegram_chat_id: "",
  });
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    getSettings().then(setForm).catch(() => {});
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

  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-xl font-bold text-slate-800">通知設定</h1>
      <p className="text-sm text-slate-500">設定後,排程爬蟲跑完有新品/降價就會推播給你。</p>

      <div className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Discord Webhook</label>
          <input
            value={form.discord_webhook}
            onChange={(e) => setForm({ ...form, discord_webhook: e.target.value })}
            placeholder="https://discord.com/api/webhooks/..."
            className={field}
          />
          <p className="mt-1 text-xs text-slate-400">
            Discord 頻道 → 編輯頻道 → 整合 → Webhook → 複製 Webhook 網址
          </p>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <label className="mb-1 block text-sm font-medium text-slate-700">Telegram Bot Token</label>
          <input
            value={form.telegram_token}
            onChange={(e) => setForm({ ...form, telegram_token: e.target.value })}
            placeholder="123456:ABC-..."
            className={field}
          />
          <label className="mb-1 mt-3 block text-sm font-medium text-slate-700">Telegram Chat ID</label>
          <input
            value={form.telegram_chat_id}
            onChange={(e) => setForm({ ...form, telegram_chat_id: e.target.value })}
            placeholder="你的 chat id"
            className={field}
          />
          <p className="mt-1 text-xs text-slate-400">
            跟 @BotFather 建立 bot 拿 token;chat id 可向 @userinfobot 詢問。
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={save} disabled={saving} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            儲存
          </button>
          <button onClick={test} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">
            儲存並測試發送
          </button>
          {msg && <span className="text-sm text-slate-500">{msg}</span>}
        </div>
      </div>
    </div>
  );
}
