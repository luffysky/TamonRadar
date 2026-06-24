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

## 後續批次(同日持續開發)
- **搜尋來源擴充**:SerpAPI / Serper / Google CSE / Tavily / Brave / SearXNG / DuckDuckGo(自動 fallback);相關性過濾(濾掉與關鍵字完全無關結果)。
- **搜尋/列表頁 vs 商品頁分流**:列表頁不顯示亂價、抽 JSON-LD 商品;免瀏覽器補 og:image;價格支援真實區間(AggregateOffer)。
- **多領域分頁**:14 種 vertical(周邊/美食/寵物/動物/旅遊/股市/創業/房產/職缺/課程/健康/3C/汽車/二手)。
- **商品卡**:分頁(每頁 20)、愛心收藏、默認佔位圖、圓形 favicon/logo。
- **收藏/追蹤**:目標價通知、價格走勢圖(SVG)。
- **使用者儀表板** `/dashboard`、**個人頭像下拉選單**。
- **通知增強**:監看價格門檻、Discord embed、每日彙整 digest。
- **AI 增強**:多商品比較、對話記憶、AI 想關鍵字、小幫手讀使用者搜尋結果。
- **多 AI 供應商**:OpenAI / Gemini / Groq / OpenRouter / Anthropic;使用者自備金鑰(加密儲存)。
- **社群**:部落格(所有使用者可寫、Tiptap + emoji/GIF/上傳、封面改上傳)、討論區(18 分類 + 讚/檢舉)。
- **帳號**:Email 驗證、改密碼、刪帳號、密碼小眼睛、分享連結(OG 分享卡)。
- **後台**:祕密路徑(ADMIN_SLUG)、CRM、ERP 營運報表、稽核日誌、站內公告(跑馬燈)、Email 群發、SEO 管理、檢舉佇列、停權、匯出 CSV、使用者詳情(完整使用記錄)、特權帳號。
- **配額**:每日免費額度(特權/付費/管理員無限)。
- **部署**:輕量 Dockerfile(無 Chromium,DISABLE_BROWSER=1);SSE 斷線重連。
- **瀏覽器擴充**(Chrome/Edge MV3)。
- **RWD 修正**:全域 overflow-x clip、儀表板/價格雷達/Tiptap 手機版面。

## 後續批次 2(通知 / 監看 / 後台深化)
- **通知三路**:站內鈴鐺(tr_notifications)+ Discord/Telegram + **Web Push(VAPID,關站也收)**;沒設個人管道也有站內。
- **共用 bot**:Telegram 只填 chat_id、Discord 填 user id(中央 bot DM),沒填走 DISCORD_WEBHOOK 共用頻道。
- **自動綁定**:網站產生綁定碼 → `/bind 碼`(Discord/Telegram)自動綁帳號,設定頁顯示已綁定。
- **監看升級**:單一監看全包(補貨/新增/下架/改價勾選)、CTA 動態偵測(行動路徑)、Shopify 商品卡抽取、可編輯、每 20 秒自動更新、遵守 robots、內嵌 JSON/SPA/RSS/API 多格式抽取。
- **後台**:側欄殼、recharts 圖表牆、爬取檢核(全站)、AI 成本明細、應用設定、Owner 權限、使用者詳情(監看/排程/搜尋結果可看/AI 對話完整內容)、Bot 對話紀錄。
- **修復**:整站爬存檔 NaN、設定 500(密文超過 VARCHAR→改 TEXT)、圖表空白、Discord 驗簽防呆。

## 資料庫(已建,共 21 表,皆 tr_ 前綴)
tr_users / tr_runs / tr_user_settings / tr_schedules / tr_watches / tr_favorites /
tr_posts / tr_threads / tr_replies / tr_subscriptions / tr_audit / tr_announcements / tr_reports /
tr_app_settings / tr_usage / tr_ai_cost / tr_notifications / tr_push_subs / tr_ai_chat_log /
tr_bot_chat_log / tr_bind_codes

## 待辦
見 [0624_todo.md](0624_todo.md) 與 [roadmap.md](roadmap.md)。
