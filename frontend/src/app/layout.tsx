import type { Metadata, Viewport } from "next";
import { Noto_Sans_TC } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { ToastProvider } from "@/components/Toast";
import Nav from "@/components/Nav";
import PWARegister from "@/components/PWARegister";

const sans = Noto_Sans_TC({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "TamonRadar 多聞情報雷達",
  description: "TamonRadar — 輸入關鍵字即時掃描多聞相關情報,自動分類、抓價格、產生報告與 AI 摘要。",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "TamonRadar", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#2f5597",
  width: "device-width",
  initialScale: 1,
};

const themeScript = `try{var t=localStorage.getItem('tr_theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW" className={sans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans">
        <PWARegister />
        <ToastProvider>
          <AuthProvider>
            <Nav />
            <main className="mx-auto max-w-6xl px-4 py-6 animate-fade-in">{children}</main>
            <footer className="mx-auto max-w-6xl px-4 py-10 text-center text-xs text-slate-400">
              TamonRadar · 多聞情報雷達 · 教學用途 · 請控制爬取頻率,勿繞過網站限制
            </footer>
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
