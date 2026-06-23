"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const ERROR_MESSAGES: Record<string, string> = {
  state: "登入驗證失效,請重試。",
  config: "後端尚未設定 Google 登入。",
  token: "無法取得 Google 授權。",
  email: "無法取得你的 email。",
  oauth: "Google 登入過程發生錯誤。",
};

export default function AuthCallbackPage() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = hash.get("token");
    const err = hash.get("error");

    if (err) {
      setError(ERROR_MESSAGES[err] ?? "登入失敗。");
      return;
    }
    if (!token) {
      setError("沒有收到登入資訊。");
      return;
    }
    getMe(token)
      .then(({ user }) => {
        signIn(token, user);
        router.replace("/");
      })
      .catch(() => setError("登入失敗,請重試。"));
  }, [signIn, router]);

  return (
    <div className="mx-auto mt-20 max-w-sm text-center">
      {error ? (
        <>
          <p className="text-sm text-rose-600">{error}</p>
          <button
            onClick={() => router.replace("/login")}
            className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700"
          >
            回登入頁
          </button>
        </>
      ) : (
        <p className="text-sm text-slate-400">登入中…</p>
      )}
    </div>
  );
}
