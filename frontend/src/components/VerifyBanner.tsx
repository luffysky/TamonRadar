"use client";

import { useState } from "react";
import { useAuth } from "./AuthProvider";
import { resendVerify } from "@/lib/api";

export default function VerifyBanner() {
  const { user } = useAuth();
  const [sent, setSent] = useState(false);
  const [hide, setHide] = useState(false);

  if (!user || user.email_verified || hide) return null;

  return (
    <div className="bg-amber-50 px-4 py-2 text-center text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
      你的 Email 尚未驗證。
      <button
        onClick={async () => { try { await resendVerify(); setSent(true); } catch { /* ignore */ } }}
        className="mx-2 font-medium underline hover:no-underline"
      >
        {sent ? "已寄出,請收信" : "重寄驗證信"}
      </button>
      <button onClick={() => setHide(true)} className="opacity-60 hover:opacity-100">✕</button>
    </div>
  );
}
