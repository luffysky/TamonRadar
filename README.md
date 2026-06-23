# 📡 TamonRadar(多聞情報雷達)

從原本的 CLI 爬蟲,升級成「前端輸入關鍵字 → 即時爬取 → 網頁渲染結果」的全端應用。

- **前端**:Next.js 14 + Tailwind(輸入、即時進度、圖表、可篩選表格、商品卡、匯出、AI 摘要、歷史)
- **後端**:FastAPI + Selenium(背景爬蟲、SSE 即時進度、報告產生、Claude AI 摘要)

```
tammon_crawler_project/
├── backend/                FastAPI + 爬蟲核心
│   ├── app.py              API:啟動/進度(SSE)/結果/停止/匯出/歷史/AI摘要
│   ├── crawler/            爬蟲核心(由舊版重構,已修 5 個資料品質問題)
│   ├── jobs.py             背景任務 + 進度事件緩衝
│   ├── history.py          歷史紀錄存檔
│   └── requirements.txt
├── frontend/               Next.js 前端
│   └── src/app, src/components, src/lib
└── (舊版 CLI 檔案保留:main.py / config.py …,仍可獨立執行)
```

## 啟動方式(開兩個終端機)

### 1) 後端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

第一次執行 Selenium 會自動下載對應版本的 ChromeDriver(需已安裝 Chrome)。

(選用)啟用 AI 摘要,設定環境變數後再啟動:

```bash
# PowerShell
$env:ANTHROPIC_API_KEY="你的key"
python -m uvicorn app:app --reload --port 8000
```

### 2) 前端

```bash
cd frontend
npm install
npm run dev
```

打開 http://localhost:3000

## 功能

- ✅ 多使用者帳號(Email 註冊/登入 + Google 第三方登入,每人有自己的歷史)
- ✅ 搜尋 API(Brave / SerpAPI)取代易被擋的 Google Selenium
- ✅ 價格雷達:跟上次比較,標出新品 / 降價 / 補貨(幣別自動換算台幣)
- ✅ 排程自動爬 + Discord / Telegram 推播
- ✅ AI 摘要、AI 對話查詢、AI 濾雜訊;角色自動標記
- ✅ 深色模式、商品圖燈箱、Toast、PWA(可安裝到桌面/手機)、RWD
- ✅ 任務佇列:限制同時爬蟲數,避免多人同時用爆記憶體
- ✅ 前端輸入關鍵字即時爬取(SSE 進度條 + 即時訊息)
- ✅ 自動分類(計分制)、抓價格(結構化優先 + 雜訊過濾)
- ✅ 統計卡片、分類/來源長條圖、商品候選卡
- ✅ 表格可搜尋 / 篩選分類 / 只看有價格 / 點欄位排序
- ✅ 匯出 CSV / Excel / Markdown 報告
- ✅ Claude AI 摘要分析
- ✅ 歷史紀錄頁(回看每次搜尋)
- ✅ 「如何運作」介紹頁(含爬蟲原理解說)

## 部署到 Zeabur(GitHub 方式)

這是 monorepo,前後端要建成 **兩個獨立服務**,都指向同一個 repo。

### 後端服務(API + 爬蟲)
1. Zeabur → Add Service → Git → 選 `TamonRadar`。
2. 設定 **Root Directory = `backend`**。
   後端有 `Dockerfile`(內含 Chromium),Zeabur 會用它建置,Selenium 才能在雲端跑。
3. 環境變數(參考 `backend/.env.example`):
   - `DATABASE_URL` = Supabase 連線字串(**雲端必填**,否則資料會在每次重部署後消失)
   - `JWT_SECRET` = 自己亂打一長串(**雲端必填**,帳號 token 的簽章密鑰)
   - `CORS_ORIGINS` = 你的前端網域(例:`https://tamonradar.zeabur.app`)
   - `BRAVE_API_KEY` 或 `SERPAPI_KEY`(**雲端強烈建議**,否則 Selenium 會被 Google 擋)
   - `SEARCH_PROVIDER`(選用,`brave`/`serpapi`/`selenium`,留空會自動依金鑰決定)
   - `ANTHROPIC_API_KEY`(選用,要 AI 摘要才需要)

### 資料庫服務(Supabase / Postgres)
在同一個 Zeabur 專案 Add Service → Supabase / PostgreSQL,把它給的連線字串填到後端的
`DATABASE_URL`。後端啟動時會自動建表(users / runs)。本機開發不設 `DATABASE_URL`
則自動用 SQLite 檔(`backend/data/tamonradar.db`)。
4. 部署完成後記下後端網域,例如 `https://tamonradar-api.zeabur.app`。

### 前端服務(Next.js)
1. 再 Add Service → 同一個 repo。
2. 設定 **Root Directory = `frontend`**(Zeabur 會自動辨識 Next.js)。
3. 環境變數(參考 `frontend/.env.example`):
   - `NEXT_PUBLIC_API_BASE` = 上面後端的網域
   - ⚠️ 這個變數是**建置時**寫進前端的,設定後要重新部署一次才生效。

### 順序小提醒
先部署後端拿到網域 → 設定前端的 `NEXT_PUBLIC_API_BASE` → 部署前端 →
最後回後端把 `CORS_ORIGINS` 補上前端網域並重啟。

> 注意:雲端爬蟲一樣可能被 Google 擋驗證(雲端 IP 更容易被盯上),這是先天限制。

## 注意

Google 可能跳驗證擋下自動搜尋,系統會標記並跳過該關鍵字。教學用途,請控制頻率、勿繞過網站限制。
