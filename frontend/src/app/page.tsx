"use client";

import { useRef, useState } from "react";
import { startCrawl, streamCrawl, stopCrawl } from "@/lib/api";
import type { CrawlResult, ProgressEvent } from "@/lib/types";
import ProgressPanel from "@/components/ProgressPanel";
import ResultsView from "@/components/ResultsView";

const DEFAULT_KEYWORDS = "多聞 週邊\n多聞 公仔\n多聞 壓克力\n現在的是哪一個多聞";

export default function HomePage() {
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS);
  const [pages, setPages] = useState(2);
  const [maxDetail, setMaxDetail] = useState(20);
  const [scrapeDetails, setScrapeDetails] = useState(true);

  const [jobId, setJobId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [result, setResult] = useState<CrawlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<(() => void) | null>(null);

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
          setError("與後端的連線中斷,請確認後端是否在執行。");
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
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <label className="text-sm font-medium text-slate-700">搜尋關鍵字(一行一個)</label>
          <textarea
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            rows={5}
            disabled={running}
            className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm focus:border-brand-500 focus:outline-none disabled:bg-slate-50"
          />

          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-slate-600">每個關鍵字頁數</span>
              <input
                type="number" min={1} max={5} value={pages} disabled={running}
                onChange={(e) => setPages(Number(e.target.value))}
                className="rounded-lg border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-slate-600">最多抓詳細頁</span>
              <input
                type="number" min={0} max={100} value={maxDetail} disabled={running}
                onChange={(e) => setMaxDetail(Number(e.target.value))}
                className="rounded-lg border border-slate-300 px-2 py-1.5"
              />
            </label>
          </div>

          <label className="mt-3 flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox" checked={scrapeDetails} disabled={running}
              onChange={(e) => setScrapeDetails(e.target.checked)}
            />
            進入每個結果頁抓詳細資訊(較慢,但價格/圖片較完整)
          </label>

          <div className="mt-4 flex gap-2">
            <button
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
          <h2 className="mb-4 text-xl font-bold text-slate-800">搜尋結果</h2>
          <ResultsView runId={jobId} result={result} />
        </section>
      )}
    </div>
  );
}
