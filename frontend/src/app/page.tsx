"use client";

import { useEffect, useRef, useState } from "react";
import {
  Radar, Sparkles, Gift, Utensils, PawPrint, Bird, Plane, TrendingUp, Rocket,
  Home as HomeIcon, Briefcase, BookOpen, HeartPulse, Laptop, Car, Recycle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { startCrawl, streamCrawl, stopCrawl, getHealth, aiKeywords, scrapePage, startSiteCrawl } from "@/lib/api";
import type { HealthInfo } from "@/lib/api";
import type { CrawlResult, ProgressEvent } from "@/lib/types";

const VERT_ICON: Record<string, LucideIcon> = {
  merch: Gift, food: Utensils, pet: PawPrint, animal: Bird, travel: Plane,
  stock: TrendingUp, startup: Rocket, realestate: HomeIcon, job: Briefcase,
  course: BookOpen, health: HeartPulse, tech: Laptop, car: Car, secondhand: Recycle,
};

const PROVIDER_LABELS: Record<string, string> = {
  serpapi: "SerpAPI",
  serper: "Serper.dev",
  googlecse: "Google 自訂搜尋(CSE)",
  tavily: "Tavily(AI 搜尋)",
  brave: "Brave Search API",
  searxng: "SearXNG(自架,開源)",
  duckduckgo: "DuckDuckGo(免金鑰)",
  selenium: "Selenium(本機開 Chrome)",
};
const PROVIDER_ORDER = ["serpapi", "serper", "googlecse", "tavily", "brave", "searxng", "duckduckgo", "selenium"];
import ProgressPanel from "@/components/ProgressPanel";
import ResultsView from "@/components/ResultsView";
import { useRequireAuth } from "@/components/AuthProvider";
import { VERTICALS, getVertical } from "@/lib/verticals";
import { useDragScroll } from "@/lib/useDragScroll";

const DEFAULT_KEYWORDS = "多聞 週邊\n多聞 公仔\n多聞 壓克力\n現在的是哪一個多聞";

export default function HomePage() {
  const { user, ready } = useRequireAuth();
  const tabDrag = useDragScroll();
  const [vertical, setVertical] = useState("merch");
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);
  const [pages, setPages] = useState(2);
  const [maxDetail, setMaxDetail] = useState(20);
  const [scrapeDetails, setScrapeDetails] = useState(true);
  const [provider, setProvider] = useState<string>("");
  const [health, setHealth] = useState<HealthInfo | null>(null);

  const [jobId, setJobId] = useState<string | null>(null);
  const [pageUrl, setPageUrl] = useState("");
  const [sitePages, setSitePages] = useState(40);
  const [siteDepth, setSiteDepth] = useState(2);
  const [pageKeywords, setPageKeywords] = useState("");
  const [sitePaths, setSitePaths] = useState("");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [result, setResult] = useState<CrawlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => {
        setHealth(h);
        setProvider(h.default_provider);
      })
      .catch(() => {});
    // 瀏覽器擴充 / 外部連結帶 ?q= 進來時預填關鍵字
    try {
      const q = new URLSearchParams(window.location.search).get("q");
      if (q) setKeywords(q);
    } catch { /* ignore */ }
  }, []);

  async function handleStart() {
    setError(null);
    setResult(null);
    setEvents([]);
    setRunning(true);

    const list = keywords.split("\n").map((k) => k.trim()).filter(Boolean);
    try {
      const { job_id } = await startCrawl({
        keywords: list,
        google_pages_per_keyword: pages,
        max_detail_pages: maxDetail,
        headless: true,
        scrape_details: scrapeDetails,
        search_provider: provider || undefined,
        vertical,
      });
      setJobId(job_id);

      closeRef.current = streamCrawl(
        job_id,
        (e) => setEvents((prev) => [...prev, e]),
        (payload) => {
          setRunning(false);
          if (payload.result) setResult(payload.result);
          if (payload.status === "error") setError(payload.error ?? "爬蟲發生錯誤");
        },
        () => {
          setRunning(false);
          setError("連線中斷(後端可能正在重新部署)。已完成的搜尋會出現在「歷史」;若沒有,稍候再重新搜尋一次。");
        }
      );
    } catch {
      setRunning(false);
      setError("無法啟動爬蟲,請確認後端 (http://127.0.0.1:8000) 是否已啟動。");
    }
  }

  function handleStop() {
    if (jobId) stopCrawl(jobId);
  }

  async function handleScrapePage() {
    const url = pageUrl.trim();
    if (!url.startsWith("http") || running) return;
    setRunning(true); setError(null); setResult(null); setEvents([]);
    try {
      const kws = pageKeywords.split(/[,,\s]+/).map((k) => k.trim()).filter(Boolean);
      const r = await scrapePage(url, kws);
      setJobId(r.run_id);
      setResult({ records: r.records, summary: r.summary });
    } catch (e) {
      setError(e instanceof Error ? e.message : "整頁抓取失敗");
    } finally {
      setRunning(false);
    }
  }

  async function handleSiteCrawl() {
    const url = pageUrl.trim();
    if (!url.startsWith("http") || running) return;
    setError(null); setResult(null); setEvents([]); setRunning(true);
    try {
      const kws = pageKeywords.split(/[,,\s]+/).map((k) => k.trim()).filter(Boolean);
      const paths = sitePaths.split(/[,,\s]+/).map((k) => k.trim()).filter(Boolean);
      const { job_id } = await startSiteCrawl(url, Math.max(1, sitePages || 40), Math.max(1, siteDepth || 2), kws, paths);
      setJobId(job_id);
      closeRef.current = streamCrawl(
        job_id,
        (e) => setEvents((prev) => [...prev, e]),
        (payload) => { setRunning(false); if (payload.result) setResult(payload.result); if (payload.status === "error") setError(payload.error ?? "整站爬發生錯誤"); },
        () => { setRunning(false); setError("連線中斷,已完成的會在「歷史」。"); }
      );
    } catch (e) {
      setRunning(false);
      setError(e instanceof Error ? e.message : "整站爬啟動失敗");
    }
  }

  function pickVertical(key: string) {
    setVertical(key);
    const v = getVertical(key);
    setKeywords(v.examples.join("\n"));
  }

  async function aiSuggest() {
    const q = window.prompt("描述你想找什麼,AI 幫你想關鍵字(例:便宜又好評的機械鍵盤)");
    if (!q) return;
    try {
      const r = await aiKeywords(q);
      if (r.keywords.length) setKeywords(r.keywords.join("\n"));
      else alert("沒有產生關鍵字(可能未設定 AI 金鑰)");
    } catch {
      alert("產生失敗,請稍後再試");
    }
  }

  if (!ready || !user) {
    return <p className="py-20 text-center text-sm text-slate-400">載入中…</p>;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-gradient-to-br from-brand-600 to-brand-500 p-6 text-white shadow">
        <h1 className="flex items-center gap-2 text-2xl font-bold"><Radar className="h-6 w-6" /> TamonRadar</h1>
        <p className="text-sm font-medium text-brand-50">多聞情報雷達</p>
        <p className="mt-2 text-sm text-brand-50">
          輸入關鍵字 → 即時掃描 Google → 自動分類、抓價格、整理成可篩選的報告與 AI 摘要。
        </p>
      </section>

      <section className="space-y-4">
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
          <div {...tabDrag} className="scroll-thin mb-3 flex w-full gap-1.5 overflow-x-auto pb-1 select-none">
            {VERTICALS.map((v) => {
              const Icon = VERT_ICON[v.key] ?? Gift;
              return (
                <button
                  key={v.key}
                  onClick={() => pickVertical(v.key)}
                  className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-sm transition ${
                    vertical === v.key
                      ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-200"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-700"
                  }`}
                >
                  <Icon className="h-4 w-4" /> {v.label}
                </button>
              );
            })}
          </div>
          <p className="mb-2 text-xs text-slate-400">{getVertical(vertical).tagline}</p>
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">搜尋關鍵字(一行一個)</label>
            <button onClick={aiSuggest} disabled={running} className="flex items-center gap-1 text-xs text-brand-600 hover:underline disabled:opacity-50 dark:text-brand-300"><Sparkles className="h-3.5 w-3.5" /> AI 想關鍵字</button>
          </div>
          <textarea
            data-tour="search"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            rows={5}
            disabled={running}
            placeholder={getVertical(vertical).placeholder}
            className="mt-2 w-full rounded-lg border border-slate-300 dark:border-slate-600 p-3 text-sm focus:border-brand-500 focus:outline-none disabled:bg-slate-50 dark:bg-slate-900"
          />

          <label className="mt-3 flex flex-col gap-1 text-sm">
            <span className="text-slate-600 dark:text-slate-300">搜尋來源</span>
            <select
              data-tour="provider"
              value={provider}
              disabled={running}
              onChange={(e) => setProvider(e.target.value)}
              className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5"
            >
              {PROVIDER_ORDER.map((p) => {
                const ok = health?.search_providers?.[p];
                return (
                  <option key={p} value={p} disabled={ok === false}>
                    {PROVIDER_LABELS[p]}
                    {ok === false ? "(未設定金鑰)" : ""}
                  </option>
                );
              })}
            </select>
            <span className="text-xs text-slate-400">
              雲端建議用 Brave / SerpAPI(穩定不被擋);Selenium 適合本機。
            </span>
          </label>

          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-slate-600 dark:text-slate-300">每個關鍵字頁數</span>
              <input
                type="number" min={1} max={20} value={pages} disabled={running}
                onChange={(e) => setPages(Number(e.target.value))}
                className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-slate-600 dark:text-slate-300">最多抓詳細頁</span>
              <input
                type="number" min={0} max={100} value={maxDetail} disabled={running}
                onChange={(e) => setMaxDetail(Number(e.target.value))}
                className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5"
              />
            </label>
          </div>

          <label className="mt-3 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox" checked={scrapeDetails} disabled={running}
              onChange={(e) => setScrapeDetails(e.target.checked)}
            />
            進入每個結果頁抓詳細資訊(較慢,但價格/圖片較完整)
          </label>

          <div className="mt-4 flex gap-2">
            <button
              data-tour="start"
              onClick={handleStart}
              disabled={running}
              className="flex-1 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {running ? "爬取中…" : "開始搜尋"}
            </button>
            {running && (
              <button
                onClick={handleStop}
                className="rounded-lg border border-rose-300 px-4 py-2 font-medium text-rose-600 hover:bg-rose-50"
              >
                停止
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-400">
            提醒:本工具一律遵守各網站 robots.txt(標明禁止的不爬)、只抓公開資料、自動節流;請勿用於侵權、轉售或大量爬取。Google 跳驗證時會自動跳過該關鍵字。
          </p>

          <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-700">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">或:整頁抓取(貼一個網址,抓出整頁所有列/商品)</label>
            <p className="mb-2 text-xs text-slate-400">適合股票排行、商品列表、排行榜這種「一頁很多項」的頁面。</p>
            <div className="flex gap-2">
              <input
                value={pageUrl}
                onChange={(e) => setPageUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScrapePage()}
                placeholder="https://… 整頁網址"
                disabled={running}
                className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900"
              />
              <button onClick={handleScrapePage} disabled={running || !pageUrl.trim().startsWith("http")} className="shrink-0 rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                抓整頁
              </button>
              <button onClick={handleSiteCrawl} disabled={running || !pageUrl.trim().startsWith("http")} title="跟著同網域連結遞迴抓(背景)" className="shrink-0 rounded-lg border border-slate-400 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-500 dark:text-slate-200 dark:hover:bg-slate-700">
                整站爬
              </button>
            </div>
            <input
              value={pageKeywords}
              onChange={(e) => setPageKeywords(e.target.value)}
              placeholder="只收含這些關鍵字的項目(選填,逗號分隔;留空=全收)"
              disabled={running}
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900"
            />
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              <label className="flex items-center gap-1.5">頁數上限
                <input type="number" min={1} max={5000} value={sitePages} onChange={(e) => setSitePages(Number(e.target.value))} className="w-20 rounded-lg border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-900" />
              </label>
              <label className="flex items-center gap-1.5">深度
                <input type="number" min={1} max={10} value={siteDepth} onChange={(e) => setSiteDepth(Number(e.target.value))} className="w-16 rounded-lg border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-900" />
              </label>
              <span>頁數可自訂(預設 40,上限 5000);頁數越多越久越吃資源,請斟酌。</span>
            </div>
            <input
              value={sitePaths}
              onChange={(e) => setSitePaths(e.target.value)}
              placeholder="整站爬:只抓特定路徑(選填,例 /products/, /item;逗號分隔;留空=整站)"
              disabled={running}
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900"
            />
          </div>
        </div>

        <ProgressPanel events={events} running={running} />
      </section>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error}
        </div>
      )}

      {result && jobId && (
        <section>
          <h2 className="mb-4 text-xl font-bold text-slate-800 dark:text-slate-100">搜尋結果</h2>
          <ResultsView runId={jobId} result={result} vertical={vertical} />
        </section>
      )}
    </div>
  );
}
