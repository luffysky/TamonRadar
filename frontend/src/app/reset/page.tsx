"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { resetPassword } from "@/lib/api";

export default function ResetPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    setToken(hash.get("token"));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("缺少重設權杖,請重新從信中的連結進入。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重設失敗");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <div className="card p-6">
        <h1 className="mb-4 text-lg font-bold text-slate-800 dark:text-slate-100">重設密碼</h1>
        {done ? (
          <p className="text-sm text-emerald-600">✅ 密碼已重設,正在帶你去登入…</p>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <input
              type="password" required value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="新密碼(至少 6 字)" autoComplete="new-password"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
            />
            {error && <p className="text-sm text-rose-600">{error}</p>}
            <button type="submit" disabled={loading} className="w-full rounded-lg bg-brand-600 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
              {loading ? "處理中…" : "設定新密碼"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
