"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { verifyEmail } from "@/lib/api";

export default function VerifyPage() {
  return (
    <Suspense fallback={<p className="py-20 text-center text-sm text-slate-400">載入中…</p>}>
      <VerifyInner />
    </Suspense>
  );
}

function VerifyInner() {
  const sp = useSearchParams();
  const [state, setState] = useState<"loading" | "ok" | "fail">("loading");

  useEffect(() => {
    const token = sp.get("token");
    if (!token) { setState("fail"); return; }
    verifyEmail(token).then(() => setState("ok")).catch(() => setState("fail"));
  }, [sp]);

  return (
    <div className="mx-auto max-w-md py-20 text-center">
      {state === "loading" && <p className="text-sm text-slate-400">驗證中…</p>}
      {state === "ok" && (
        <>
          <div className="text-4xl">✅</div>
          <h1 className="mt-3 text-xl font-bold text-slate-800 dark:text-slate-100">Email 已驗證!</h1>
          <p className="mt-1 text-sm text-slate-500">感謝你,帳號已完成驗證。</p>
          <Link href="/" className="mt-4 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">回首頁</Link>
        </>
      )}
      {state === "fail" && (
        <>
          <div className="text-4xl">⚠️</div>
          <h1 className="mt-3 text-xl font-bold text-slate-800 dark:text-slate-100">驗證連結無效或已過期</h1>
          <p className="mt-1 text-sm text-slate-500">請登入後在橫幅點「重寄驗證信」。</p>
          <Link href="/login" className="mt-4 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">前往登入</Link>
        </>
      )}
    </div>
  );
}
