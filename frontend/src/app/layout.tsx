import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "TamonRadar 多聞情報雷達",
  description: "TamonRadar — 輸入關鍵字即時掃描多聞相關情報,自動分類、抓價格、產生報告與 AI 摘要。",
};

function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold text-brand-600">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-base text-white">📡</span>
          <span>TamonRadar</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/" className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100">搜尋</Link>
          <Link href="/history" className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100">歷史紀錄</Link>
          <Link href="/about" className="rounded-md px-3 py-1.5 text-slate-600 hover:bg-slate-100">如何運作</Link>
        </nav>
      </div>
    </header>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body>
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-10 text-center text-xs text-slate-400">
          TamonRadar · 多聞情報雷達 · 教學用途 · 請控制爬取頻率,勿繞過網站限制
        </footer>
      </body>
    </html>
  );
}
