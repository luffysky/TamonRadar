import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Noto_Sans_TC } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { ToastProvider } from "@/components/Toast";
import Nav from "@/components/Nav";
import AnnouncementBanner from "@/components/AnnouncementBanner";
import VerifyBanner from "@/components/VerifyBanner";
import PWARegister from "@/components/PWARegister";
import AssistantWidget from "@/components/AssistantWidget";
import CookieConsent from "@/components/CookieConsent";
import OnboardingTour from "@/components/OnboardingTour";

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
            <AnnouncementBanner />
            <Nav />
            <VerifyBanner />
            <main className="mx-auto max-w-6xl px-4 py-6 animate-fade-in">{children}</main>
            <footer className="mt-10 border-t border-slate-200 dark:border-slate-700">
              <div className="mx-auto max-w-6xl space-y-2 px-4 py-8 text-center text-xs text-slate-400">
                <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
                  <Link href="/about" className="hover:text-brand-600 dark:hover:text-brand-300">關於</Link>
                  <Link href="/blog" className="hover:text-brand-600 dark:hover:text-brand-300">部落格</Link>
                  <Link href="/forum" className="hover:text-brand-600 dark:hover:text-brand-300">討論區</Link>
                  <Link href="/privacy" className="hover:text-brand-600 dark:hover:text-brand-300">隱私權政策</Link>
                  <Link href="/terms" className="hover:text-brand-600 dark:hover:text-brand-300">服務條款</Link>
                  <Link href="/cookies" className="hover:text-brand-600 dark:hover:text-brand-300">Cookie 政策</Link>
                </div>
                <div>© {new Date().getFullYear()} TamonRadar. All rights reserved.</div>
              </div>
            </footer>
            <AssistantWidget />
            <CookieConsent />
            <OnboardingTour />
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
