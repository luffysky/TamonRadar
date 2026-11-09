# 📡 TamonRadar(多聞情報雷達)

從原本的 CLI 爬蟲,升級成「前端輸入關鍵字 → 即時爬取 → 網頁渲染結果」的全端應用。

- **前端**:Next.js 15 + React 19 + Tailwind(輸入、即時進度、圖表、可篩選表格、商品卡、匯出、AI 摘要、歷史)
- **後端**:FastAPI + Neon Postgres(DB 工作佇列、輪詢進度、報告產生、AI 摘要;Vercel Functions)

```
tammon_crawler_project/
├── backend/                FastAPI + 爬蟲核心
│   ├── app.py              API:啟動/進度(輪詢)/結果/停止/匯出/歷史/AI摘要
│   ├── crawler/            爬蟲核心(由舊版重構,已修 5 個資料品質問題)
│   ├── jobs.py             持久化工作佇列(認領/心跳/斷點/事件)
│   ├── worker.py           工作者:時間預算內執行工作
│   ├── scheduler.py        每分鐘派發器
│   ├── migrate.py          資料庫結構遷移(migrations/*.sql)
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
pip install -r requirements-dev.txt
python -m uvicorn app:app --reload --port 8000
```

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
- ✅ 持久化任務佇列:每人/全站併發限制、斷點續跑、崩潰回收
- ✅ 前端輸入關鍵字即時爬取(進度輪詢 + 即時訊息)
- ✅ 自動分類(計分制)、抓價格(結構化優先 + 雜訊過濾)
- ✅ 統計卡片、分類/來源長條圖、商品候選卡
- ✅ 表格可搜尋 / 篩選分類 / 只看有價格 / 點欄位排序
- ✅ 匯出 CSV / Excel / Markdown 報告
- ✅ Claude AI 摘要分析
- ✅ 歷史紀錄頁(回看每次搜尋)
- ✅ 「如何運作」介紹頁(含爬蟲原理解說)

## 部署到 Vercel(前後端兩個專案)

後端是無狀態的 Python Function:任務、事件、斷點、派發時間全部存在 Neon Postgres,Function 回應後被凍結也不影響。

### 架構重點

- **爬蟲工作**:`POST /api/crawl` 只寫一筆 `tr_jobs`(queued)並嘗試自我觸發工作者,立即回應。工作者由 Vercel Cron 每分鐘(`/api/internal/worker`)或自我觸發叫起,在時間預算內(`WORKER_BUDGET_SECONDS`,預設 240 秒,遠低於 800 秒上限)認領執行,預算用完把斷點寫回 DB 放回佇列,下一輪接續。整站爬的待抓佇列在 `tr_crawl_frontier`,單頁寫入一個交易。心跳逾時(`JOB_STALE_SECONDS`)會回收並重試,圍欄 token 擋住舊工作者。觸發遺失只會多等下一次 cron。
- **派發器**:`/api/internal/dispatch` 每分鐘用 `next_run_at` + `FOR UPDATE SKIP LOCKED` 認領到期的排程、監看、推播、每日彙整、目標價掃描與清理,在同一交易裡建立工作,重疊或重試的 cron 不會重複觸發。
- **進度**:前端輪詢 `/api/crawl/{id}/events`(事件表 `tr_job_events`,保留 `JOB_EVENT_RETENTION_DAYS` 天)。停止請求寫 DB,工作者讀到旗標後收尾。
- **限流**:`tr_rate_limits`(固定視窗,跨實例共用);DB 連不上時退回單一實例記憶體。
- **檔案**:上傳由瀏覽器預簽直傳 R2;超過 4 MB 的匯出放到 R2 私有路徑,回傳短效簽名網址。
- **機器人**:webhook 立即回應,AI 回答走工作佇列。

### 步驟

1. **遷移資料庫結構**(部署前,在本機執行,需要 Neon 直連網址):

   ```bash
   cd backend
   pip install -r requirements-dev.txt
   DATABASE_URL_UNPOOLED=... python migrate.py          # 只套用尚未執行的版本
   DATABASE_URL_UNPOOLED=... python migrate.py --verify  # 比對 ORM 與資料庫
   ```

   應用程式啟動時不跑 DDL。之後的結構變更一律新增 `migrations/000N_*.sql`。

2. **匯入舊資料**(只讀舊庫,可重跑,會逐表比對筆數):

   ```bash
   python scripts/load_old_db.py --source <舊 Postgres 網址> --target <新庫直連網址>
   ```

   匯入後排程/監看的 `next_run_at` 由派發器依上次執行時間自動補上,不會全部立刻重跑。

3. **後端專案**:Vercel 新增專案 → Root Directory = `backend`、Framework = FastAPI(入口 `app:app`)、Region 由 `backend/vercel.json` 指定 `sin1`。`vercel.json` 已含兩個每分鐘 cron 與 `maxDuration: 800`。

4. **前端專案**:Root Directory = `frontend`,環境變數 `NEXT_PUBLIC_API_BASE` = 後端網址(**建置時**寫入,改了要重新部署)。

5. **回頭設定**:
   - 後端 `CORS_ORIGINS` 補上前端網域。
   - Cloudflare R2 bucket 的 CORS 允許前端網域 `PUT`(`Content-Type` 標頭),否則瀏覽器直傳會失敗。
   - 建議在 R2 為 `exports/` 前綴設定 1 天到期的生命週期規則。
   - 用管理員帳號呼叫 `POST /api/admin/telegram/setup` 重設 Telegram webhook、到 Discord 開發者後台把 Interactions Endpoint 改成新後端網址。

### 後端環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `DATABASE_URL` | ✅ | Neon **pooled** 連線字串(含 `-pooler`) |
| `DATABASE_URL_UNPOOLED` | 遷移時 | Neon 直連,只有 `migrate.py` / 匯入腳本使用 |
| `CRON_SECRET` | ✅ | 內部端點 Bearer;沒設時工作者與派發器一律拒絕(fail closed),Vercel Cron 會自動帶上 |
| `APP_ENV` | ✅ | `production` |
| `JWT_SECRET`、`ENCRYPTION_KEY` | ✅ | 不可相同;沿用舊值,否則既有登入與加密資料失效 |
| `ADMIN_EMAILS`、`OWNER_EMAILS` | ✅ | 管理員 |
| `CORS_ORIGINS` | ✅ | 前端網址(逗號分隔) |
| `R2_ACCOUNT_ID`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_BUCKET_NAME`、`R2_URL` | ✅ | 上傳與大型匯出 |
| `OAUTH_REDIRECT_BASE`、`FRONTEND_URL`、`GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET` | 選 | Google 登入 |
| `SEARCH_PROVIDER`、`BRAVE_API_KEY`、`SERPAPI_KEY`、`SERPER_API_KEY`、`TAVILY_API_KEY`… | 建議 | 搜尋來源;Vercel 上沒有瀏覽器,**請勿用 selenium** |
| `OPENAI_API_KEY` 等 AI 金鑰 | 選 | 見 `backend/.env.example` |
| `TELEGRAM_BOT_TOKEN`、`TELEGRAM_WEBHOOK_SECRET`、`DISCORD_PUBLIC_KEY`、`DISCORD_APP_ID`、`DISCORD_BOT_TOKEN` | 選 | 機器人 |
| `VAPID_PUBLIC_KEY`、`VAPID_PRIVATE_KEY`、`VAPID_SUBJECT`、`RESEND_API_KEY`… | 選 | 推播 / 寄信 |
| `WORKER_TRIGGER_BASE` | 選 | 自我觸發的網址;預設用 Vercel 自動提供的 `VERCEL_PROJECT_PRODUCTION_URL` |
| `WORKER_BUDGET_SECONDS` | 選 | 每輪工作者時間預算,預設 240 |
| `JOB_STALE_SECONDS` | 選 | 心跳逾時回收,預設 180 |
| `MAX_CONCURRENT_CRAWLS` | 選 | 全站同時爬蟲數,預設 5 |
| `DB_POOL_SIZE`、`DB_MAX_OVERFLOW` | 選 | 預設 1 / 4;`DB_POOL_SIZE=0` 改用 NullPool |
| `JOB_EVENT_RETENTION_DAYS`、`JOB_RETENTION_DAYS`、`SYSTEM_JOB_RETENTION_DAYS`、`PRICE_OBSERVATION_RETENTION_DAYS` | 選 | 保留天數,預設 7 / 30 / 3 / 365 |

### 本機開發

沒設 `DATABASE_URL` 時用 SQLite 並自動建表。沒有 Cron,想讓工作者跑可手動 `curl -H "Authorization: Bearer $CRON_SECRET" localhost:8000/api/internal/worker`。要用 Selenium 開瀏覽器:`pip install -r requirements-selenium.txt`,或用 `Dockerfile.selenium`。

> 注意:雲端爬蟲一樣可能被 Google 擋驗證,這是先天限制。

## 注意

Google 可能跳驗證擋下自動搜尋,系統會標記並跳過該關鍵字。教學用途,請控制頻率、勿繞過網站限制。
