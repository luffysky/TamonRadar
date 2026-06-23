import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "TamonRadar 多聞情報雷達",
  description: "TamonRadar — 輸入關鍵字即時掃描多聞相關情報,自動分類、抓價格、產生報告與 AI 摘要。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body>
        <AuthProvider>
          <Nav />
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
          <footer className="mx-auto max-w-6xl px-4 py-10 text-center text-xs text-slate-400">
            TamonRadar · 多聞情報雷達 · 教學用途 · 請控制爬取頻率,勿繞過網站限制
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
