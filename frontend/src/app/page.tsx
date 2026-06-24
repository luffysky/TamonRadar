"use client";

import { useEffect, useRef, useState } from "react";
import { startCrawl, streamCrawl, stopCrawl, getHealth, aiKeywords, scrapePage } from "@/lib/api";
import type { HealthInfo } from "@/lib/api";
import type { CrawlResult, ProgressEvent } from "@/lib/types";

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

const DEFAULT_KEYWORDS = "多聞 週邊\n多聞 公仔\n多聞 壓克力\n現在的是哪一個多聞";

export default function HomePage() {
  const { user, ready } = useRequireAuth();
  const [vertical, setVertical] = useState("merch");
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);
  const [pages, setPages] = useState(2);
  const [maxDetail, setMaxDetail] = useState(20);
  const [scrapeDetails, setScrapeDetails] = useState(true);
  const [provider, setProvider] = useState<string>("");
  const [health, setHealth] = useState<HealthInfo | null>(null);

  const [jobId, setJobId] = useState<string | null>(null);
  const [pageUrl, setPageUrl] = useState("");
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
      const r = await scrapePage(url);
      setJobId(r.run_id);
      setResult({ records: r.records, summary: r.summary });
    } catch (e) {
      setError(e instanceof Error ? e.message : "整頁抓取失敗");
    } finally {
      setRunning(false);
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
        <h1 className="text-2xl font-bold">📡 TamonRadar</h1>
        <p className="text-sm font-medium text-brand-50">多聞情報雷達</p>
        <p className="mt-2 text-sm text-brand-50">
          輸入關鍵字 → 即時掃描 Google → 自動分類、抓價格、整理成可篩選的報告與 AI 摘要。
        </p>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
          <div className="scroll-thin mb-3 flex w-full gap-1.5 overflow-x-auto pb-1">
            {VERTICALS.map((v) => (
              <button
                key={v.key}
                onClick={() => pickVertical(v.key)}
                className={`flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border px-3 py-1.5 text-sm transition ${
                  vertical === v.key
                    ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-200"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-700"
                }`}
              >
                <span>{v.icon}</span> {v.label}
              </button>
            ))}
          </div>
          <p className="mb-2 text-xs text-slate-400">{getVertical(vertical).tagline}</p>
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">搜尋關鍵字(一行一個)</label>
            <button onClick={aiSuggest} disabled={running} className="text-xs text-brand-600 hover:underline disabled:opacity-50 dark:text-brand-300">✨ AI 想關鍵字</button>
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
            提醒:Google 可能跳出驗證而擋下自動搜尋,系統會標記並跳過該關鍵字。請勿大量爬取。
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
            </div>
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
          <ResultsView runId={jobId} result={result} />
        </section>
      )}
    </div>
  );
}
