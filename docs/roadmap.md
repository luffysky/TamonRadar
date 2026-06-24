# TamonRadar Roadmap / TODO

> 做法:一批一批做,每批編譯/測過再 push。完成的項目用 ~~刪除線~~ 標記、不刪掉。金流最後接。

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

### Batch 3 — SEO / GEO(讓 Google 與 AI 都爬得到)
- [ ] robots.txt(允許一般與 AI 爬蟲:GPTBot、ClaudeBot、PerplexityBot…)
- [ ] sitemap.xml(動態,含部落格/討論區頁)
- [ ] 每頁 metadata(title/description/OG/Twitter card)
- [ ] JSON-LD 結構化資料(Organization、Article、Discussion…)
- [ ] GEO:給 AI 易讀的內容結構、llms.txt
- [ ] 後台 SEO 管理(編輯各頁 title/description/關鍵字)

### Batch 4 — 部落格(Blog)
- [ ] 文章資料表 + 後台撰寫/編輯(管理員)
- [ ] 公開文章列表 + 內頁(SSR、利於 SEO)
- [ ] 分類/標籤、Markdown 內文、封面圖

### Batch 5 — 討論區(Forum)
- [ ] 分類、主題串、回覆 資料表
- [ ] 分類(先建好):旅遊、攝影、烹飪、動漫、周邊、演唱會/活動、3C科技、
      遊戲、運動、美食、寵物、時尚美妝、理財、汽機車、影視音樂、生活雜談…
- [ ] 發文/回覆/讚、登入才能發、基本檢舉
- [ ] 分類頁 + 主題頁(SSR 利於 SEO)

### Batch 6 — CRM(顧客關係管理,後台)
- [ ] 使用者詳情:備註、標籤、活動紀錄(登入、搜尋、AI 用量)
- [ ] 篩選/搜尋使用者、匯出
- [ ] 站內公告 / Email 群發(用 Resend)

### Batch 7 — ERP(務實子集,配合本產品)
- [ ] 訂閱/方案管理(配合金流)
- [ ] 收入/用量報表(AI 成本、API 用量、活躍度)
- [ ] 供應/額度管理(各 API 金鑰用量監控)
  > 註:完整 ERP(進銷存/財會/HR)超出本產品範疇,只做與營運相關的務實部分。

### Batch 8 — 資料/分析功能
- [ ] 價格走勢圖(同商品多次歷史折線)
- [ ] 收藏/追蹤清單 + 目標價通知
- [ ] 首頁儀表板總覽

### Batch 9 — 監看/通知增強
- [ ] 價格門檻通知(低於 X 元)
- [ ] JS 網站監看(Selenium 備援)
- [ ] 每日彙整 digest
- [ ] 通知附縮圖 / Discord embed

### Batch 10 — AI 增強
- [ ] AI 幫想關鍵字、多商品比較、對話記憶

### Batch 11 — 帳號/體驗
- [ ] Email 驗證、修改密碼、刪除帳號、GitHub 登入、分享公開連結、瀏覽器擴充

### Batch 12 — 收費(金流最後接)
- [ ] 方案/配額系統(監看數/頻率/AI 次數依方案放行)
- [ ] 金流(Stripe 或綠界 ECPay)
