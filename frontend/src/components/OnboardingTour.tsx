"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";

interface Step {
  target?: string;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  { title: "歡迎使用 TamonRadar 👋", body: "花 30 秒帶你認識主要功能,隨時可以略過。" },
  { target: '[data-tour="search"]', title: "1. 輸入關鍵字", body: "在這裡一行一個輸入想搜尋的主題,系統會即時搜尋並自動整理。" },
  { target: '[data-tour="provider"]', title: "2. 選搜尋來源", body: "雲端建議用 SerpAPI 或 Brave(穩定不會被擋);Selenium 適合本機。" },
  { target: '[data-tour="start"]', title: "3. 開始搜尋", body: "按下去就會即時顯示進度與結果,還能用 AI 幫你抓重點、濾雜訊。" },
  { target: '[data-tour="assistant"]', title: "4. AI 小幫手", body: "任何使用上的問題,點這顆隨時問我。準備好了就開始吧!" },
];

export default function OnboardingTour() {
  const { user, ready } = useAuth();
  const pathname = usePathname();
  const [step, setStep] = useState(0);
  const [show, setShow] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (ready && user && pathname === "/") {
      try {
        if (!localStorage.getItem("tr_onboarded")) setShow(true);
      } catch {
        /* ignore */
      }
    }
  }, [ready, user, pathname]);

  const current = STEPS[step];

  useEffect(() => {
    if (!show) return;
    if (!current?.target) {
      setRect(null);
      return;
    }
    const el = document.querySelector(current.target) as HTMLElement | null;
    if (!el) {
      setRect(null);
      return;
    }
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    const update = () => setRect(el.getBoundingClientRect());
    update();
    const t = setTimeout(update, 350);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [show, step, current]);

  if (!show || !user || pathname !== "/") return null;

  function done() {
    try {
      localStorage.setItem("tr_onboarded", "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }

  const last = step === STEPS.length - 1;
  const pad = 8;
  const spot = rect
    ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }
    : null;

  // 提示卡位置:夾在視窗內,目標下方優先,空間不夠放上方;沒有目標就置中
  const vw = typeof window !== "undefined" ? window.innerWidth : 400;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const cardW = Math.min(320, vw - 24);
  let card: React.CSSProperties;
  if (spot) {
    const left = Math.min(Math.max(12, spot.left), vw - cardW - 12);
    const below = spot.top + spot.height + 12;
    const top = below + 220 < vh ? below : Math.max(12, spot.top - 232);
    card = { position: "fixed", top, left, width: cardW };
  } else {
    card = { position: "fixed", top: "50%", left: "50%", width: cardW, transform: "translate(-50%,-50%)" };
  }

  return (
    <div className="fixed inset-0 z-[60]">
      {/* 沒有 spotlight 時用整片暗背景 */}
      {!spot && <div className="absolute inset-0 bg-black/60" />}

      {/* spotlight:用大範圍 box-shadow 把目標以外變暗 */}
      {spot && (
        <div
          className="pointer-events-none absolute rounded-xl ring-2 ring-brand-400 transition-all duration-300"
          style={{
            top: spot.top,
            left: spot.left,
            width: spot.width,
            height: spot.height,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0.62)",
          }}
        />
      )}

      {/* 提示卡 */}
      <div style={card} className="animate-scale-in w-[min(20rem,calc(100vw-24px))] rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl dark:border-slate-700 dark:bg-slate-800">
        <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">{current.title}</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{current.body}</p>

        <div className="mt-3 flex items-center justify-center gap-1.5">
          {STEPS.map((_, i) => (
            <span key={i} className={`h-1.5 rounded-full transition-all ${i === step ? "w-5 bg-brand-600" : "w-1.5 bg-slate-300 dark:bg-slate-600"}`} />
          ))}
        </div>

        <div className="mt-3 flex items-center justify-between">
          <button onClick={done} className="text-sm text-slate-400 hover:underline">略過</button>
          <div className="flex gap-2">
            {step > 0 && (
              <button onClick={() => setStep((x) => x - 1)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">上一步</button>
            )}
            <button onClick={() => (last ? done() : setStep((x) => x + 1))} className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700">
              {last ? "開始使用" : "下一步"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
