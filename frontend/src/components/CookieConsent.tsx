"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Cookie } from "lucide-react";

export default function CookieConsent() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem("tr_cookie_ok")) setShow(true);
    } catch {
      /* ignore */
    }
  }, []);

  if (!show) return null;

  function accept() {
    try {
      localStorage.setItem("tr_cookie_ok", "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }

  return (
    <div className="animate-slide-up fixed bottom-4 left-1/2 z-50 w-[min(34rem,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-start gap-3">
        <Cookie className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
        <div className="text-sm text-slate-600 dark:text-slate-300">
          本網站使用必要的 Cookie 來維持登入與基本功能。繼續使用即表示你同意我們的{" "}
          <Link href="/cookies" className="text-brand-600 underline dark:text-brand-300">Cookie 政策</Link>。
        </div>
      </div>
      <div className="mt-3 flex justify-end">
        <button onClick={accept} className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700">
          我知道了
        </button>
      </div>
    </div>
  );
}
