"use client";

import { useEffect, useState } from "react";
import { BellRing } from "lucide-react";
import { getPushKey, subscribePush, unsubscribePush } from "@/lib/api";

function urlB64ToUint8(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export default function PushToggle() {
  const [state, setState] = useState<"unsupported" | "off" | "on" | "busy">("off");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      setState("unsupported");
      return;
    }
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => setState(sub ? "on" : "off"))
      .catch(() => {});
  }, []);

  async function enable() {
    setState("busy");
    setMsg("");
    try {
      const key = await getPushKey();
      if (!key) { setMsg("後端尚未設定推播金鑰(VAPID)"); setState("off"); return; }
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { setMsg("你拒絕了通知權限"); setState("off"); return; }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(key) });
      await subscribePush(sub.toJSON() as unknown as PushSubscription);
      setState("on");
      setMsg("✅ 已開啟,關著網站也會收到系統通知");
    } catch {
      setMsg("開啟失敗");
      setState("off");
    }
  }

  async function disable() {
    setState("busy");
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) { await unsubscribePush(sub.endpoint); await sub.unsubscribe(); }
      setState("off");
      setMsg("已關閉");
    } catch {
      setState("on");
    }
  }

  if (state === "unsupported") {
    return <p className="text-xs text-slate-400">此瀏覽器不支援系統推播(iOS 需先「加入主畫面」成 App)。</p>;
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={state === "on" ? disable : enable}
        disabled={state === "busy"}
        className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 ${
          state === "on" ? "border border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300" : "bg-brand-600 text-white hover:bg-brand-700"
        }`}
      >
        <BellRing className="h-4 w-4" /> {state === "on" ? "關閉系統通知" : "開啟系統通知(關站也收得到)"}
      </button>
      {msg && <span className="text-xs text-slate-500 dark:text-slate-400">{msg}</span>}
    </div>
  );
}
