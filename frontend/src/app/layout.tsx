import type { Metadata, Viewport } from "next";
import { Noto_Sans_TC } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { ToastProvider } from "@/components/Toast";
import Nav from "@/components/Nav";
import PWARegister from "@/components/PWARegister";
import AssistantWidget from "@/components/AssistantWidget";

const sans = Noto_Sans_TC({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans",
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tamonradar.snowrealm.pet";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "TamonRadar 多聞情報雷達 — 搜尋、價格雷達、到貨/開賣通知",
    template: "%s | TamonRadar",
  },
  description:
    "TamonRadar 是搜尋與情報監看工具:輸入任何關鍵字即時搜尋、自動整理、AI 摘要;還能排程自動搜尋、監看到貨/開賣並即時推播通知。",
  keywords: ["TamonRadar", "價格雷達", "到貨通知", "開賣通知", "搶票提醒", "AI 搜尋", "比價", "監看"],
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "TamonRadar", statusBarStyle: "default" },
  icons: { icon: "/favicon.ico", shortcut: "/favicon.ico", apple: "/icon-192.png" },
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "TamonRadar",
    title: "TamonRadar 多聞情報雷達",
    description: "搜尋、價格雷達、到貨/開賣即時通知,還有 AI 幫你抓重點。",
    url: SITE_URL,
    locale: "zh_TW",
  },
  twitter: {
    card: "summary_large_image",
    title: "TamonRadar 多聞情報雷達",
    description: "搜尋、價格雷達、到貨/開賣即時通知,還有 AI 幫你抓重點。",
  },
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
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "TamonRadar",
              alternateName: "多聞情報雷達",
              url: SITE_URL,
              description:
                "搜尋與情報監看工具:即時搜尋、AI 摘要、價格雷達、到貨/開賣即時通知。",
              inLanguage: "zh-TW",
            }),
          }}
        />
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
            <AssistantWidget />
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
