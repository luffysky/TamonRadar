"use client";

import { useEffect, useState } from "react";
import { Search, Radar, CalendarClock, Sparkles, X } from "lucide-react";
import { useAuth } from "./AuthProvider";

const STEPS = [
  {
    icon: Sparkles,
    title: "歡迎使用 TamonRadar 👋",
    body: "這是一個搜尋 + 情報監看工具。花 30 秒帶你看怎麼用。",
  },
  {
    icon: Search,
    title: "1. 搜尋任何主題",
    body: "在首頁輸入關鍵字(一行一個),系統會即時搜尋、自動分類、抓價格,還能用 AI 幫你抓重點。",
  },
  {
    icon: Radar,
    title: "2. 監看到貨 / 開賣",
    body: "在「監看」貼上商品或票券網址,從「未開賣/售完」變成「可購買」時,會立刻通知你去搶。",
  },
  {
    icon: CalendarClock,
    title: "3. 排程 + 通知",
    body: "在「排程」設定自動搜尋,並到「設定」填好 Discord / Telegram,變化就推播到你手機。",
  },
];

export default function OnboardingTour() {
  const { user, ready } = useAuth();
  const [step, setStep] = useState(0);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (ready && user) {
      try {
        if (!localStorage.getItem("tr_onboarded")) setShow(true);
      } catch {
        /* ignore */
      }
    }
  }, [ready, user]);

  if (!show || !user) return null;

  function done() {
    try {
      localStorage.setItem("tr_onboarded", "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }

  const s = STEPS[step];
  const Icon = s.icon;
  const last = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4">
      <div className="w-[min(26rem,100%)] rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-800">
        <div className="flex justify-end">
          <button onClick={done} className="rounded-full p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white">
          <Icon className="h-7 w-7" />
        </div>
        <h2 className="mt-4 text-center text-lg font-bold text-slate-800 dark:text-slate-100">{s.title}</h2>
        <p className="mt-2 text-center text-sm leading-relaxed text-slate-600 dark:text-slate-300">{s.body}</p>

        <div className="mt-5 flex items-center justify-center gap-1.5">
          {STEPS.map((_, i) => (
            <span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? "w-5 bg-brand-600" : "w-1.5 bg-slate-300 dark:bg-slate-600"}`} />
          ))}
        </div>

        <div className="mt-5 flex items-center justify-between">
          <button onClick={done} className="text-sm text-slate-400 hover:underline">略過</button>
          <button
            onClick={() => (last ? done() : setStep((x) => x + 1))}
            className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            {last ? "開始使用" : "下一步"}
          </button>
        </div>
      </div>
    </div>
  );
}
