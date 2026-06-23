function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-600 font-bold text-white">
        {n}
      </div>
      <div>
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
        <div className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{children}</div>
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-bold text-slate-800 dark:text-slate-100">{title}</h2>
      {children}
    </div>
  );
}

export default function AboutPage() {
  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-gradient-to-br from-slate-800 to-slate-700 p-6 text-white shadow">
        <h1 className="text-2xl font-bold">TamonRadar 怎麼運作?</h1>
        <p className="mt-2 text-sm text-slate-200">
          TamonRadar 是一個「網頁化的爬蟲」:前端(Next.js)負責畫面與互動,後端(Python FastAPI)
          負責真正用瀏覽器去 Google 搜尋、進入網頁抓資料,再把整理好的結果即時回傳給你看。
        </p>
      </section>

      <Card title="使用流程">
        <div className="space-y-5">
          <Step n={1} title="輸入關鍵字">
            在首頁一行一個輸入想查的關鍵字(例如「多聞 公仔」),設定要抓幾頁、要不要進詳細頁,按「開始搜尋」。
          </Step>
          <Step n={2} title="即時看進度">
            後端開始爬之後,進度會透過 <code className="rounded bg-slate-100 dark:bg-slate-700 px-1">SSE</code>(伺服器即時推播)
            一條一條傳回來,你會看到「正在搜尋 X、找到 N 筆、抓第幾頁」這種即時訊息與進度條。
          </Step>
          <Step n={3} title="看整理好的結果">
            爬完後會自動產生:統計卡片、分類/來源長條圖、商品候選卡(含圖片價格)、以及可篩選排序搜尋的完整表格。
          </Step>
          <Step n={4} title="後續動作">
            可一鍵匯出 CSV / Excel / Markdown 報告;按「AI 分析」用 Claude 幫你判斷哪些是真商品、哪些重複;
            每次搜尋也會存進「歷史紀錄」供回看比較。
          </Step>
        </div>
      </Card>

      <Card title="爬蟲是怎麼抓資料的?">
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
          這是整個系統的核心。後端用 <strong>Selenium</strong> 開一個真的 Chrome 瀏覽器(無頭模式,看不到視窗),
          模擬人去搜尋,流程分成五步:
        </p>
        <ol className="space-y-3 text-sm text-slate-700 dark:text-slate-200">
          <li>
            <strong>1. Google 搜尋</strong> — 對每個關鍵字開
            <code className="mx-1 rounded bg-slate-100 dark:bg-slate-700 px-1">google.com/search</code>,
            用多組 CSS selector 抓標題、網址、摘要(Google 的 HTML 結構常變,所以多重兼容)。
          </li>
          <li>
            <strong>2. 還原真實網址</strong> — Google 的連結常包一層
            <code className="mx-1 rounded bg-slate-100 dark:bg-slate-700 px-1">/url?q=…</code>,程式會把真正網址解出來。
          </li>
          <li>
            <strong>3. 去重複 + 過濾</strong> — 相同網址只留一筆,並濾掉圖片/壓縮檔等不該爬的連結。
          </li>
          <li>
            <strong>4. 進入詳細頁</strong> — 逐一打開結果頁,用 <strong>BeautifulSoup</strong>
            解析 title、meta、og:image、結構化價格(JSON-LD)等。
          </li>
          <li>
            <strong>5. 分類與抓價</strong> — 用關鍵字<strong>計分</strong>判斷分類,並用多種規則抓出最可能的售價。
          </li>
        </ol>
        <p className="mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
          ⚠️ 每個動作之間會隨機等 2–5 秒,降低被判定成機器人的機率。即使如此,Google 仍可能跳驗證頁;
          遇到時系統會標記並跳過該關鍵字,不會卡住。請務必控制頻率、勿繞過網站限制。
        </p>
      </Card>

      <Card title="資料品質:我們修掉的問題">
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">早期版本有幾個讓資料不可信的問題,這版都處理了:</p>
        <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-200">
          <li>💰 <strong>價格更準</strong> — 不再從整頁文字硬抓第一個數字(會抓到運費/樓層/0 元),
            改成優先讀結構化價格、過濾雜訊值、用出現頻率挑出真正售價。</li>
          <li>🏷️ <strong>分類更分散</strong> — 從「命中就回傳」改成<strong>計分制</strong>,
            標題權重高於內文,不再幾乎全部被歸成「周邊」。</li>
          <li>🚫 <strong>減少誤判攔截</strong> — 不再因頁面出現 “sorry” 就誤標成被擋。</li>
          <li>🧹 <strong>更乾淨的連結</strong> — 帶參數的圖片網址(如 <code>.png?x=1</code>)也能正確排除。</li>
        </ul>
      </Card>

      <Card title="技術架構">
        <div className="grid gap-3 sm:grid-cols-2 text-sm">
          <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3">
            <p className="font-semibold text-slate-700 dark:text-slate-200">前端 · Next.js + Tailwind</p>
            <p className="mt-1 text-slate-500 dark:text-slate-400">畫面、互動、SSE 進度、圖表、表格、匯出按鈕。</p>
          </div>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3">
            <p className="font-semibold text-slate-700 dark:text-slate-200">後端 · FastAPI + Selenium</p>
            <p className="mt-1 text-slate-500 dark:text-slate-400">背景執行緒跑爬蟲、SSE 推進度、產生報告、Claude AI 摘要。</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
