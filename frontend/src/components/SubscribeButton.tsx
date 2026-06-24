"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, BellOff } from "lucide-react";
import { useAuth } from "./AuthProvider";
import { isSubscribed, subscribeAuthor, unsubscribeAuthor } from "@/lib/api";

export default function SubscribeButton({ authorId }: { authorId: number }) {
  const { user } = useAuth();
  const [sub, setSub] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) isSubscribed(authorId).then(setSub).catch(() => {});
  }, [user, authorId]);

  if (!user) {
    return <Link href="/login" className="inline-flex items-center gap-1.5 rounded-lg bg-white/20 px-3 py-1.5 text-sm hover:bg-white/30"><Bell className="h-4 w-4" /> 登入後訂閱</Link>;
  }
  if (user.id === authorId) return null;

  async function toggle() {
    setBusy(true);
    try {
      if (sub) { await unsubscribeAuthor(authorId); setSub(false); }
      else { await subscribeAuthor(authorId); setSub(true); }
    } catch { /* ignore */ } finally { setBusy(false); }
  }

  return (
    <button onClick={toggle} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50">
      {sub ? <><BellOff className="h-4 w-4" /> 已訂閱(取消)</> : <><Bell className="h-4 w-4" /> 訂閱新文通知</>}
    </button>
  );
}
