# TamonRadar Roadmap / TODO

> 做法:一批一批做,每批編譯/測過再 push。完成的項目用 ~~刪除線~~ 標記、不刪掉。金流最後接。

## ⚠️ 需要設定的環境變數(新增的記得補上 Zeabur)
**後端**:DATABASE_URL、JWT_SECRET、ADMIN_EMAILS、CORS_ORIGINS、BRAVE_API_KEY/SERPAPI_KEY、
SEARCH_PROVIDER、OPENAI_API_KEY/ANTHROPIC_API_KEY/**GEMINI_API_KEY/GROQ_API_KEY/OPENROUTER_API_KEY**(+各模型)、
GOOGLE_CLIENT_ID/SECRET、OAUTH_REDIRECT_BASE、FRONTEND_URL、RESEND_API_KEY/RESEND_FROM、GMAIL_*、TWD_PER_*、
**R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET_NAME/R2_URL(檔案上傳)**、
**ENCRYPTION_KEY(設定加密)**、**TELEGRAM_BOT_TOKEN/TELEGRAM_WEBHOOK_SECRET/DISCORD_PUBLIC_KEY/DISCORD_APP_ID/DISCORD_BOT_TOKEN(AI 機器人)**、
**SEARXNG_URL(自架搜尋,選用)**
**前端**:NEXT_PUBLIC_API_BASE、NEXT_PUBLIC_SITE_URL、**NEXT_PUBLIC_GIPHY_API_KEY(GIF/貼圖)**

### 近期完成(追加)
- ~~UI 全面換 lucide icon、AI 對話重做、UX 動畫(slide/scale/按鈕微互動)~~
- ~~手機側邊抽屜(右→左滑入、滿視口高)~~
- ~~吉祥物 logo + favicon 修正~~
- ~~Spotlight 新手導覽(聚焦照亮 + 逐步說明)~~
- ~~法律頁(隱私/條款/Cookie)+ 頁尾版權 + Cookie 同意~~
- ~~富文本編輯器(Tiptap)+ emoji + Giphy GIF/貼圖 + R2 上傳(圖片/影片/音樂/任意檔案)→ 接入部落格與討論區~~
- ~~BYO AI 金鑰擴充:OpenAI/Gemini/Groq/OpenRouter/Anthropic~~
- ~~敏感設定(AI金鑰/Discord/TG)加密存 DB、讀取解密~~
- ~~TG/Discord 接上 AI(共用機器人:Telegram webhook + Discord interactions)~~
- ~~搜尋來源加 SearXNG(自架開源)+ DuckDuckGo(免金鑰)+ 自動 fallback~~
- ~~輕量 Dockerfile(雲端免 Chromium)+ SSE 斷線自動重連/補抓~~


## ✅ 已完成(基礎)
- ~~搜尋 API(Brave/SerpAPI,serp 優先自動 fallback)~~
- ~~多使用者帳號 + Google 登入 + 忘記密碼(Resend/Gmail)~~
- ~~價格雷達(新品/降價/補貨 + 幣別換算)~~
- ~~排程(APScheduler)+ Discord/Telegram 推播~~
- ~~監看(到貨/開賣通知)~~
- ~~AI 摘要/對話/濾雜訊(通用、主題感知)+ 角色標記~~
- ~~BYO AI 金鑰(使用者自備)~~
- ~~深色模式 / 燈箱 / Toast / PWA / RWD~~

## 批次進度

### Batch 1 — 管理員後台 + 使用量地基 ✅
- ~~User 加 plan/ai_used 欄位~~
- ~~AI 每次呼叫累加使用量~~
- ~~管理員身份(ADMIN_EMAILS)~~
- ~~/api/admin/stats、/api/admin/users、設定方案~~
- ~~前台 /admin 頁(統計卡 + 使用者表)~~

### Batch 2 — 前台 AI 助手 ✅
- ~~網站知識庫~~
- ~~/api/assistant 問答端點~~
- ~~全站浮動 AI 助手 widget~~

### Batch 3 — SEO / GEO(讓 Google 與 AI 都爬得到)✅
- ~~robots.txt(允許一般與 AI 爬蟲:GPTBot、ClaudeBot、PerplexityBot…)~~
- ~~sitemap.xml(動態)~~
- ~~每頁 metadata(title/description/OG/Twitter card)~~
- ~~JSON-LD 結構化資料(WebSite、Article)~~
- ~~GEO:llms.txt~~
- [ ] 後台 SEO 管理(編輯各頁 title/description/關鍵字)← 之後做

### Batch 4 — 部落格(Blog)✅
- ~~文章資料表 + 後台撰寫/編輯(管理員)~~
- ~~公開文章列表 + 內頁(SSR、利於 SEO,含 Article JSON-LD)~~
- ~~分類、Markdown 內文、封面圖~~

### Batch 5 — 討論區(Forum)✅
- ~~分類、主題串、回覆 資料表~~
- ~~18 個分類:演唱會/活動、周邊、動漫、遊戲、3C、旅遊、攝影、烹飪、美食、運動、
      寵物、時尚美妝、理財、汽機車、影視音樂、書籍、健康、生活雜談~~
- ~~發文/回覆、登入才能發、作者或管理員可刪~~
- ~~分類總覽 + 分類頁 + 主題頁(Markdown 內文)~~
- [ ] 之後:讚、檢舉、主題頁改 SSR 強化 SEO

### Batch 6 — CRM(顧客關係管理,後台)✅(部分)
- ~~使用者詳情:備註、標籤、活動統計(搜尋/監看/排程/發文/AI用量)~~
- ~~搜尋使用者、清單連到詳情~~
- [ ] 站內公告 / Email 群發(用 Resend)← 之後

### Batch 6.5 — UI/品牌 ✅(進行中)
- ~~改用 lucide-react icon(減少 emoji)~~
- ~~AI 對話元件重新設計(氣泡/頭像/動畫)~~
- ~~手機漢堡選單(RWD)~~
- [ ] 全站其餘 emoji 逐步換 icon

### Batch 6.6 — 法律 / 頁尾 / 導覽 ✅
- ~~隱私權政策、服務條款、Cookie 政策 頁面~~
- ~~Cookie 同意橫幅~~
- ~~頁尾:移除「教學用途」,改 © 版權 + 法律連結~~
- ~~新使用者上手導覽(登入後的多步引導)~~

### Batch 7 — ERP(務實子集,配合本產品)✅(報表部分)
- ~~營運報表:使用者/活躍/AI用量/內容數(文章/主題/回覆)/近7天新註冊/AI用量排行/方案分布~~
- [ ] 訂閱管理(等金流)、收入報表(等金流)
  > 註:完整 ERP(進銷存/財會/HR)超出本產品範疇,只做與營運相關的務實部分。

### Batch 8 — 資料/分析功能 ✅
- ~~價格走勢圖(同商品多次歷史折線,SVG)~~
- ~~收藏/追蹤清單 + 目標價通知(排程跑完檢查)~~
- ~~使用者儀表板 /dashboard 總覽~~

### 後台安全 ✅
- ~~/admin 藏到祕密路徑(NEXT_PUBLIC_ADMIN_SLUG)+ 後端 API 權限把關~~
- ~~about 頁完整功能一覽(隨時更新)~~

### Batch 9 — 監看/通知增強
- [ ] 價格門檻通知(低於 X 元)
- [ ] JS 網站監看(Selenium 備援)
- [ ] 每日彙整 digest
- [ ] 通知附縮圖 / Discord embed

### Batch 10 — AI 增強
- ~~AI 幫想關鍵字~~
- [ ] 多商品比較、對話記憶

### Batch 11 — 帳號/體驗
- ~~修改密碼、刪除帳號~~
- [ ] Email 驗證、GitHub 登入、分享公開連結、瀏覽器擴充

### Batch 12 — 收費(金流最後接)
- [ ] 方案/配額系統(監看數/頻率/AI 次數依方案放行)
- [ ] 金流(Stripe 或綠界 ECPay)
