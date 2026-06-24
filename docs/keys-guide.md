# 金鑰 / 服務申請教學

> 每個都「選用」:沒設只是該功能停用,核心搜尋仍可用(DuckDuckGo 免金鑰永遠當備援)。
> 申請完把值填到 **後端 Zeabur 服務的 Variables**(前端的填前端服務)。

---

## 🔍 搜尋 API

### SerpAPI(Google 結果,免費 100/月)
1. 到 https://serpapi.com 註冊
2. Dashboard → **Api Key** 複製
3. 後端設 `SERPAPI_KEY`

### Serper.dev(Google 結果,註冊送 2500 次)
1. 到 https://serper.dev 用 Google 註冊
2. 進 Dashboard → **API Key** 複製
3. 後端設 `SERPER_API_KEY`

### Google 自訂搜尋 CSE(每天免費 100)
需要**兩個值**:
1. **搜尋引擎 ID(cx)**:到 https://programmablesearchengine.google.com → 「新增搜尋引擎」→ 搜尋整個網路 → 建立 → 複製「搜尋引擎 ID」→ 填 `GOOGLE_CSE_ID`
2. **API Key**:到 https://console.cloud.google.com → 建專案 → 「API 和服務 → 程式庫」→ 啟用「Custom Search API」→ 「憑證 → 建立憑證 → API 金鑰」→ 複製 → 填 `GOOGLE_CSE_KEY`

### Tavily(AI 搜尋,免費 1000/月)
1. 到 https://tavily.com 註冊
2. Dashboard → 複製 **API Key**(tvly-...)
3. 後端設 `TAVILY_API_KEY`

### Brave Search API(免費 2000/月)
1. 到 https://brave.com/search/api/ → 註冊、選 **Free** 方案(要綁卡但不收費)
2. 拿 **Subscription Token** → 填 `BRAVE_API_KEY`
   ⚠️ 免費版限每秒 1 次(系統已自動節流)

### SearXNG(開源自架,完全免費、不被擋)⭐
1. 在 Zeabur 專案 **Add Service → 搜尋 "SearXNG"** 模板部署(或自己用 Docker `searxng/searxng`)
2. 部署後在它的 Settings 開 **Public Networking / Generate Domain**,拿到網址
3. 確認該實例有開啟 JSON 格式(SearXNG 設定 `search.formats` 要含 `json`)
4. 後端設 `SEARXNG_URL=https://你的searxng網域`

### DuckDuckGo
免金鑰,免設定(雲端 IP 可能被限流,當備援用)。

---

## 🤖 AI(要哪家填哪家;使用者也可在「設定」自備)
- **OpenAI**:https://platform.openai.com → API keys → Create → `OPENAI_API_KEY`
- **Google Gemini**:https://aistudio.google.com/apikey → 建立 → `GEMINI_API_KEY`
- **Groq**(超快、免費):https://console.groq.com/keys → `GROQ_API_KEY`
- **OpenRouter**(一把鑰匙多家):https://openrouter.ai/keys → `OPENROUTER_API_KEY`
- **Anthropic**:https://console.anthropic.com → API Keys → `ANTHROPIC_API_KEY`

---

## 📨 寄信(忘記密碼)
### Resend(免費 3000/月)
1. https://resend.com 註冊 → API Keys → Create → `RESEND_API_KEY`
2. (正式)到 Domains 驗證你的網域,`RESEND_FROM` 用該網域的信箱
### Gmail SMTP(備援)
1. Google 帳號開**兩步驟驗證** → 「應用程式密碼」產生 16 碼
2. `GMAIL_USER`=你的 gmail、`GMAIL_APP_PASSWORD`=那 16 碼(不含空格)

---

## 🎫 Telegram 機器人(讓使用者跟 AI 對話)
1. 在 Telegram 找 **@BotFather** → 傳 `/newbot` → 取名 → 拿到 **token**(像 `123456:ABC...`)
2. 後端設 `TELEGRAM_BOT_TOKEN`=那個 token、`TELEGRAM_WEBHOOK_SECRET`=自己取一個字串
3. 後端 redeploy 後,到 **後台 /console-x7k2 → 按「設定 Telegram 機器人」**(會自動 setWebhook)
4. 在 Telegram 跟你的 bot 對話即可

> 排程/監看通知的「個人 Telegram」是另一回事:在網站「設定」填你自己的 bot token + chat id(向 @userinfobot 問 chat id)。

---

## 💬 Discord 機器人(/ask 指令問 AI)
1. 到 https://discord.com/developers/applications → **New Application**
2. **General Information** → 複製 **Application ID** → `DISCORD_APP_ID`;複製 **Public Key** → `DISCORD_PUBLIC_KEY`
3. **Bot** 分頁 → Reset Token → 複製 → `DISCORD_BOT_TOKEN`
4. **General Information → Interactions Endpoint URL** 填:`https://你的後端網域/api/discord/interactions` → 存檔(Discord 會驗證,需後端已部署且 DISCORD_PUBLIC_KEY 正確)
5. 後端 redeploy 後,到後台按 **「註冊 Discord 指令」**(註冊 `/ask`)
6. 把 bot 邀請進你的伺服器(OAuth2 → URL Generator → scopes 勾 `applications.commands`)
7. 在 Discord 打 `/ask 你的問題`

---

## 🗂️ Cloudflare R2 檔案上傳(部落格/討論區附圖/影片/音樂)
1. 登入 Cloudflare → 左側 **R2** → **Create bucket**(取名,例 `tamonradar`)→ 記下 bucket 名 → `R2_BUCKET_NAME`
2. 進該 bucket → **Settings → Public access** → 開啟,拿到 **`pub-xxxx.r2.dev`** 網址 → `R2_URL=https://pub-xxxx.r2.dev`
3. R2 首頁右上 **Account ID**(或網址列那串 32 碼 hex)→ `R2_ACCOUNT_ID`
4. R2 → **Manage R2 API Tokens → Create API Token** → 權限選 **Object Read & Write**、範圍選該 bucket → 建立
5. 複製 **Access Key ID** → `R2_ACCESS_KEY_ID`;**Secret Access Key** → `R2_SECRET_ACCESS_KEY`(只顯示一次!)

---

## 🔐 其他必填(雲端)
- `DATABASE_URL`:Supabase/Postgres 連線字串
- `JWT_SECRET`:亂打一長串(`python gen_secret.py` 可產生)
- `ENCRYPTION_KEY`:亂打一長串(加密使用者金鑰用)
- `ADMIN_EMAILS`:你的 email(管理員)
- `CORS_ORIGINS`:前端網域
- 前端 `NEXT_PUBLIC_API_BASE`:後端網域、`NEXT_PUBLIC_SITE_URL`:前端網域、
  `NEXT_PUBLIC_ADMIN_SLUG`:後台祕密路徑、`NEXT_PUBLIC_GIPHY_API_KEY`:Giphy(https://developers.giphy.com)
