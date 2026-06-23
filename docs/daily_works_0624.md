# 工作日誌 2026-06-24

## 主軸
把 `tammon_crawler_project` 從 CLI 爬蟲升級成全端 Web 應用 **TamonRadar(多聞情報雷達)**,並部署到 Zeabur。

## 今日完成
- **品牌**:命名 TamonRadar,全站(前後端、報告、README)套用。
- **架構**:Next.js 前端 + FastAPI 後端 + Supabase(Postgres);monorepo 推上 GitHub(luffysky/TamonRadar)。
- **資料品質修正(5 項)**:價格抽取、分類計分制、攔截誤判、URL 副檔名、空資料防呆。
- **Phase 1** 搜尋 API:Brave / SerpAPI 取代 Google Selenium(雲端不被擋)。
- **Phase 1b** 資料庫 + 多使用者帳號(JWT、pbkdf2)+ 任務佇列(併發上限)。
- **第三方登入**:Google OAuth。
- **Phase 2** 價格雷達:新品/降價/補貨比較 + 幣別換算。
- **Phase 3** 排程(APScheduler)+ Discord / Telegram 推播。
- **Phase 4** AI:對話查詢、濾雜訊、角色自動標記。
- **Phase 5** 美化:深色模式、燈箱、Toast、Noto Sans TC、RWD、PWA(可安裝)。

## 部署設定(使用者已完成)
- Zeabur 後端(Root=backend、Dockerfile 含 Chromium)、前端(Root=frontend)、Supabase。
- 環境變數 DATABASE_URL / JWT_SECRET / BRAVE_API_KEY / CORS_ORIGINS / NEXT_PUBLIC_API_BASE 已填。
- 後端網域:`tamonradar-backend.snowrealm.pet`。

## 待辦
見 [0624_todo.md](0624_todo.md)。
