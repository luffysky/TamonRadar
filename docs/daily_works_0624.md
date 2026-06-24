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

## 後續批次 3(後台/部落格深化 + 各 tab 量身分析)
- **R1 稽核**:tr_audit 擴充(target_type/changes/ip)、篩選/分頁/CSV、敏感動作(AI金鑰/停權/特權/審核/精選/推播)記錄。
- **R2 KPI**:/admin/kpi — DAU/WAU/MAU/新註冊/搜尋、活躍漏斗、每日趨勢圖、CSV。
- **R3 AI 成本**:近 30 天成本趨勢圖。
- **R4 推播中心**:/admin/broadcasts — 站內(含 Web Push)/Email/TG/Discord 多管道一次發全體。(備註:分群/排程未做)
- **R5 閱讀體驗**:閱讀進度條、瀏覽數、上一篇/下一篇、相關文章。
- **R6 留言進階**:巢狀回覆、留言讚、emoji 反應 + tr_post_comment_likes / tr_post_reactions。
- **R7 AI 寫作助手**:編輯器「寫整篇/大綱/潤飾」(走後台 AI 金鑰)。(備註:AI 封面/SEO 未做)
- **R8 密碼文章**:密碼保護 + 前台解鎖。(備註:預覽 token 未做)
- **深度情報**:insights.py + /api/insights;商品比價/划算分 + 各 tab 專屬 facets,全 vertical 顯示。

## 後續批次 4(情報再深化 + 推播完善)
- 跨次比較:跟上次同關鍵字搜尋比價(變便宜/變貴/新增/消失)。
- AI 結構化洞察 + **可點實體**(購買建議/風險/行情解讀 + 附最佳CP/最低價/好價連結)。
- R7 補完:AI 產 SEO 摘要標籤、AI 生成封面(存 R2)。
- R8 補完:草稿預覽 token(/blog/preview/[token])。
- 新增 6 個 tab:票券/租屋/遊戲/加密貨幣/機票住宿/醫美補教(各自 facets)。
- 推播中心:分群(全體/特權/已驗證/TG/Discord)+ 排程發送(tr_scheduled_broadcasts,每分鐘檢查)。
- 各 tab 分析做深:金額解析(萬/k/範圍)、每垂直專屬面向(租金設備/票價座位/薪資經驗/幣種主題/航空公司/料理供應…)+ headline 一句話總結。

## 後續批次 5(抓取/圖表/過濾)
- 整站爬移除 40 頁寫死 → 前端自訂頁數/深度(預設40、上限5000,SITE_MAX_PAGES_CAP env 可調)。
- 抓整頁 / 整站爬 新增「選填關鍵字過濾」(留空全收;填了只收標題/摘要/網址含關鍵字的項目)。
- 分類統計/來源網站圖:改回動態 recharts 但用穩定寫法(數字 height + 掛載後渲染 + debounce);summary 空時自動從 records 重算。
- 修相關性過濾過兇:中英分開斷詞 + 中文 2-gram(「Python線上課程」→ python/線上/課程)。
- 後台總覽新增「環境變數檢查」面板(只回布林,看哪些 env 沒填)。

## 後續批次 6(圖表鑽取 + 路徑過濾)
- 圖表鑽取:點分類統計/來源網站長條 → 篩選下方商品/列表/表格(再點或清除取消、未選長條淡化)。
- 整站爬:選填「只抓特定路徑」(path 含 /products/ 等才收;仍遞迴找連結)。

## 資料庫(已建,共 26 表,皆 tr_ 前綴)
tr_users / tr_runs / tr_user_settings / tr_schedules / tr_watches / tr_favorites /
tr_posts / tr_post_comments / tr_post_likes / tr_post_comment_likes / tr_post_reactions /
tr_threads / tr_replies / tr_subscriptions / tr_audit / tr_announcements / tr_reports /
tr_app_settings / tr_usage / tr_ai_cost / tr_notifications / tr_push_subs / tr_ai_chat_log /
tr_bot_chat_log / tr_bind_codes / tr_scheduled_broadcasts

## 待辦
見 [0624_todo.md](0624_todo.md) 與 [roadmap.md](roadmap.md)。
