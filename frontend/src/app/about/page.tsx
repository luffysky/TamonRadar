import type { Metadata } from "next";
import { pageMeta } from "@/lib/seo";

export async function generateMetadata(): Promise<Metadata> {
  return pageMeta("/about", {
    title: "關於 / 運作原理",
    description: "TamonRadar 怎麼運作:多來源搜尋、價格雷達、AI 助手與完整功能說明。",
  });
}

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

      <Card title="完整功能一覽">
        <div className="grid gap-2 text-sm text-slate-600 dark:text-slate-300 sm:grid-cols-2">
          <div>🔍 多來源搜尋(SerpAPI / Serper / Google CSE / Tavily / Brave / SearXNG / DuckDuckGo)</div>
          <div>📡 價格雷達:新品 / 降價 / 補貨(自動換算台幣)</div>
          <div>⏰ 排程自動搜尋 + Discord / Telegram 推播</div>
          <div>🗂️ 多領域分頁:周邊 / 美食 / 寵物 / 旅遊 / 股市 / 創業 等 14 種,各有專屬入口</div>
          <div>🎫 監看到貨 / 開賣 / 降到目標價即時通知(Discord embed)</div>
          <div>❤️ 收藏 / 追蹤 + 目標價通知 + 價格走勢圖、價格區間</div>
          <div>🤖 AI 摘要 / 對話(記憶) / 濾雜訊 / 多商品比較 / 幫想關鍵字(GPT/Gemini/Groq/OpenRouter/Claude,可自備金鑰)</div>
          <div>💬 AI 小幫手(讀你的搜尋結果,能比價、找代購;登入後出現)</div>
          <div>📝 部落格(人人可寫)+ 討論區(18 分類 + 讚 / 檢舉,Tiptap + emoji / GIF / 上傳)</div>
          <div>🔗 一鍵分享結果(產生 OG 分享卡)</div>
          <div>👤 個人儀表板、Google 登入、Email 驗證、深色模式、PWA、瀏覽器擴充</div>
          <div>🛠️ 管理後台:統計、CRM、營運報表、稽核、公告、Email 群發、SEO、檢舉、停權</div>
          <div>📊 每日免費額度(特權 / 付費無限)</div>
        </div>
      </Card>

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

      <Card title="爬蟲規範與合規(我們的原則)">
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
          TamonRadar 以「彙整公開資訊、導流回原網站」為目的,並遵守以下規範:
        </p>
        <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-200">
          <li>🤖 <strong>尊重 robots.txt</strong> — 每個網域抓取前先讀並快取其 robots 規則,<strong>明文禁止的路徑一律不爬</strong>。</li>
          <li>🐢 <strong>低頻、慢速</strong> — 動作間隨機間隔、限制頁數與深度,避免造成對方伺服器負擔;請勿設過短的監看間隔。</li>
          <li>📰 <strong>只取公開資料</strong> — 抓取公開頁面的標題、價格、縮圖、結構化資料(JSON-LD / RSS / 公開 API);不破解付費牆、不竊取隱私資料。</li>
          <li>🔗 <strong>導流而非取代</strong> — 結果一律附上原始連結與來源,鼓勵使用者前往原網站完成購買/閱讀。</li>
          <li>🔐 <strong>登入內容</strong> — 僅在你本人擁有合法存取權、且符合該站條款的前提下進行;不會散布或轉售他人受保護內容。</li>
          <li>🚫 <strong>不做違法用途</strong> — 不用於 DDoS、大量帳號攻擊、繞過防護或任何違反法律與網站條款的行為。</li>
          <li>📩 <strong>移除請求</strong> — 網站方若希望不被收錄,可透過 robots.txt 封鎖,或來信告知,我們會配合下架。</li>
        </ul>
        <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
          使用者亦須遵守:請依各網站服務條款與當地法律使用本工具,並對自己設定的爬取/監看行為負責。
        </p>
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
