# TamonRadar Roadmap / TODO

> 做法:一批一批做,每批編譯/測過再 push。金流最後接。

## ✅ 已完成
- 搜尋 API(Brave/SerpAPI,serp 優先自動 fallback)
- 多使用者帳號 + Google 登入 + 忘記密碼(Resend/Gmail)
- 價格雷達(新品/降價/補貨 + 幣別換算)
- 排程(APScheduler)+ Discord/Telegram 推播
- 監看(到貨/開賣通知)
- AI 摘要/對話/濾雜訊(通用、主題感知)+ 角色標記
- BYO AI 金鑰(使用者自備)
- 深色模式 / 燈箱 / Toast / PWA / RWD

## 🚧 待辦(依批次)

### Batch 1 — 管理員後台 + 使用量地基
- [ ] User 加欄位:plan(free/pro)、ai_used(AI 使用次數)
- [ ] AI 每次呼叫累加使用量
- [ ] 管理員身份(用 ADMIN_EMAILS 環境變數判定)
- [ ] /api/admin/stats:總人數、依 provider/plan 分布、AI 總使用量、runs/watches 數
- [ ] /api/admin/users:使用者清單(email、註冊時間、provider、plan、AI 用量)
- [ ] 前台 /admin 頁(統計卡 + 使用者表),Nav 僅管理員可見

### Batch 2 — 前台 AI 助手(問網站任何問題)
- [ ] 網站知識庫(說明文件餵給 AI)
- [ ] /api/assistant 問答端點(帶知識庫)
- [ ] 前台浮動「AI 助手」widget,任何頁都能問

### Batch 3 — 資料/分析功能
- [ ] 價格走勢圖(同商品多次歷史折線)
- [ ] 收藏/追蹤清單 + 目標價通知
- [ ] 首頁儀表板(監看中、最近降價、排程狀態總覽)

### Batch 4 — 監看/通知增強
- [ ] 價格門檻通知(低於 X 元才通知)
- [ ] JS 網站監看(Selenium 備援)
- [ ] 每日彙整 digest
- [ ] 通知附縮圖/Discord embed 卡片

### Batch 5 — AI 增強
- [ ] AI 幫想關鍵字(自然語言 → 多組搜尋詞)
- [ ] 多商品比較
- [ ] 對話記憶

### Batch 6 — 帳號/體驗
- [ ] Email 驗證、修改密碼、刪除帳號
- [ ] GitHub 登入
- [ ] 分享搜尋結果公開連結
- [ ] 瀏覽器擴充(一鍵加監看)

### Batch 7 — 收費地基(金流後面接)
- [ ] 方案/配額系統(監看數、頻率、AI 次數依方案放行)
- [ ] Free / Pro / Event 方案邏輯
- [ ] 金流(Stripe 或綠界 ECPay)— 最後做
