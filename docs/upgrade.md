# TamonRadar（多聞情報雷達）— 可以升級的地方

> 2026-08-18 寫。作者讀過 `backend/`（31 個 py 檔）、`crawler/`、
> `frontend/` 與 `extension/` 之後的判斷，不是複述 README。
>
> 對照組是 `D:\SnowRealmRebirth\1page`。

---

## 一、這個專案在做什麼、現在到哪裡

從 CLI 爬蟲升級成的全端情報雷達：前端輸入關鍵字 → 即時爬取 →
網頁渲染結果 + AI 摘要。

```text
後端    FastAPI + Selenium，31 個 py 檔
        app.py 一個檔案 **2044 行 / 149 個端點**
        auth / crypto / money / mailer / notify / push / scheduler /
        watcher / radar / insights / knowledge / bots / oauth_google
前端    Next.js 14 + Tailwind
另有    Chrome extension、舊版 CLI（保留可獨立執行）
測試    0
```

**先說做得好的地方，因為它們決定了下面的優先序**：

```text
爬蟲有節制      crawler/robots.py 有 robots.txt 檢查，
                detail_scraper 每次抓之前先問 robots.allowed(url)；
                min_sleep 2.0 / max_sleep 5.0 隨機延遲。
                這是負責任的爬蟲該有的樣子，而且很多人不做
密碼雜湊        PBKDF2-HMAC-SHA256 + 每人不同的 salt +
                hmac.compare_digest 比對（防時序攻擊）。做對了
SQL             全專案 0 處 f-string 拼接的 SQL。用 SQLAlchemy select
敏感設定加密     crypto.py 用 Fernet，存進資料庫前加密
```

**問題不在這些，在一個很安靜的地方。**

---

## 二、最該先修的三件事

### 1. 🔴 所有機密都有「開發用預設值」——沒設環境變數時，它安靜地照常運作

```python
# backend/auth.py:13
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-secret-change-me")

# backend/crypto.py
secret = os.environ.get("ENCRYPTION_KEY") or os.environ.get("JWT_SECRET") or "dev-insecure-key"

# backend/app.py:338
if secret != os.environ.get("TELEGRAM_WEBHOOK_SECRET", "tamon"):
```

⚠️ **這三行的共同點是：忘了設，程式不會抱怨。**

它會啟動、會發 token、會「加密」、會驗 webhook——每一件事看起來都正常。
而實際上：

```text
JWT_SECRET 沒設    → 任何人照著原始碼裡那串字就能簽出有效的登入 token。
                     不需要密碼、不需要漏洞，抄一行字串就好
ENCRYPTION_KEY 沒設 → 退到 JWT_SECRET；兩個都沒設 → 退到 "dev-insecure-key"。
                     資料庫裡那些 enc:v1: 開頭的欄位（AI 金鑰、
                     Discord / Telegram 憑證）任何人都解得開
TELEGRAM_WEBHOOK    → 預設 "tamon"。任何人都可以偽造 webhook
```

`crypto.py` 的檔頭其實寫了「正式建議獨立設 ENCRYPTION_KEY」——
**建議是不夠的**。這正是 1page 反覆記的那條的另一面：
**安靜的降級比明顯的失敗危險得多**，因為前者不會有人發現。

**修法（很小，但方向要對）**：

```python
def _require_secret(name: str) -> str:
    """正式環境沒設就**不要啟動**。

    開發用預設值的問題不是它不安全，是它讓「忘了設」變成
    一個沒有任何症狀的錯誤——而部署上線那天沒有人會去確認。
    """
    value = os.environ.get(name)
    if value:
        return value
    if os.environ.get("ENV", "dev") == "dev":
        # 開發時仍然給預設值，但**每次啟動都要吵**
        print(f"⚠️  {name} 未設定，正在使用開發用預設值。正式環境會拒絕啟動。")
        return f"dev-insecure-{name.lower()}"
    raise RuntimeError(f"{name} 未設定。正式環境不接受預設值。")
```

⚠️ **改完之後故意不設環境變數跑一次**，確認正式模式真的起不來。
「加了檢查」與「檢查真的會擋」是兩件事——1page 一天之內抓到過
三個名不副實的綠燈。

順帶：`ENCRYPTION_KEY` 退回 `JWT_SECRET` 這條路本身也該拿掉。
兩把鑰匙共用一個祕密，代表換 JWT_SECRET（一件應該可以隨時做的事）
會讓資料庫裡所有加密欄位**同時解不開**——而那會在換完之後
才被發現，那時舊的祕密可能已經沒有了。

### 2. `app.py` 一個檔案 2044 行、149 個端點

31 個 py 檔裡，功能模組（auth / crypto / money / mailer / notify /
push / scheduler / watcher / radar / insights）都分得很乾淨——
**唯獨路由層全部擠在一個檔案裡**。

149 個端點意味著平均每 13.7 行一個端點，也就是說：
它們大多很短，真正的邏輯確實在那些模組裡。所以這不是「義大利麵」，
是「一個太長的目錄」。

但它已經開始造成具體的成本：

```text
搜尋成本    要改「AI 摘要」那條，得在 2044 行裡找
衝突成本    任何兩個人同時改任何兩個端點都會撞在同一個檔案
理解成本    149 個端點裡哪些需要登入、哪些不用，
            沒有任何地方看得出來——要一行一行讀
```

**修法（照現有的模組邊界切，不要重新設計）**：

```text
FastAPI 的 APIRouter，一個模組一個 routers/*.py：
  routers/auth.py       登入、註冊、OAuth、重設密碼
  routers/crawl.py      啟動、進度(SSE)、結果、停止
  routers/export.py     匯出、歷史
  routers/ai.py         摘要、金鑰設定
  routers/notify.py     Discord / Telegram / push
  routers/billing.py    money.py 對應的那些
app.py 只留 include_router 與 middleware
```

⚠️ **這件事排第二不是因為它比第 3 點重要**，是因為它是第 3 點的前提：
在 2044 行的檔案上補測試，第一步就會卡在「這個端點要怎麼單獨叫起來」。

⚠️ 而且切的時候會順便回答一個現在沒人答得出的問題：
**149 個端點裡有幾個忘了加登入檢查**。切檔案時逐一看過一次，
比任何靜態分析都有效。

### 3. 31 個 py 檔、0 個測試——而其中有 `money.py`

沒有測試框架、沒有 CI。而這個專案裡有：

```text
money.py       錢
auth.py        PBKDF2 + JWT
crypto.py      Fernet 加解密
app.py:793     免費額度（FREE_AI_DAILY / FREE_SEARCH_DAILY）
crawler/       5 個「已修的資料品質問題」（README 自己說的）
```

⚠️ **不要從覆蓋率開始。** 三條就夠：

```text
1. crypto：加密再解密，拿得回原文；而且用**不同的 key** 解不開
   （第二半才是重點——沒有它，一個把 key 忽略掉的 bug 會過關）
2. auth：正確密碼過、錯誤密碼不過、被竄改的 token 不過
3. money / 額度：用完之後第 N+1 次真的被擋
```

`pytest` 加進 `requirements.txt`，三個檔案，一個下午。
然後**每一條寫完就故意把程式改壞一次**，確認它真的會紅。

⚠️ 那句 README 裡的「已修 5 個資料品質問題」——
**那五個現在沒有任何東西守著**。改壞了會安靜地回到修之前的行為，
而爬蟲的輸出本來就雜，沒有人看得出差別。那五個各補一條測試，
價值比任何新功能都高。

---

## 三、可以從 1page 搬過去的（已經驗證過，不是想法）

```text
fail closed 而不是 fail open   第 1 點。安靜的降級比明顯的失敗危險得多。
                               1page 的 .env 檢查是「缺了就不讓它跑」，
                               不是「缺了就用預設值」

故意改壞驗守衛                 每加一個測試就把程式改壞一次，改壞的方式
                               要對應它宣稱要擋的那件事。
                               ⚠️ 對第 3 點的 crypto 測試特別重要：
                               「加密再解密拿得回原文」這條，
                               即使 encrypt 是 identity 函式也會過

「反過來問」型的守衛            不要列「這個端點要驗登入」，要問
                               「149 個端點裡有哪幾個沒有驗」。
                               前者每加一個端點都要記得補，
                               後者自己會發現下一次。
                               刻意公開的要列進具名清單並寫理由

.env.example 只放名字           值一律留空，附一行說明從哪裡拿。
                               範例檔放真值遲早會被複製到別的地方
```

---

## 四、不建議做的事

```text
❌ 重寫爬蟲                  robots.txt 檢查 + 2–5 秒隨機延遲已經做對了，
                            而那是這類專案最容易做錯、也最容易惹麻煩的地方。
                            不要動它

❌ 換掉 SQLAlchemy / FastAPI  現在的選型沒問題，0 處 SQL 拼接證明用得也對

❌ 刪掉舊版 CLI              README 說它「仍可獨立執行」。
                            那是一個真的備援路徑——網頁版壞掉時還有東西可用。
                            ⚠️ 但要確認它現在**真的還跑得動**；
                            跑不動的備援比沒有備援更糟

❌ 追測試覆蓋率              三條（crypto / auth / 額度）加上那五個
                            資料品質修正，已經涵蓋 90% 的實際損失

❌ 現在拆 microservice        31 個 py 檔還不到需要拆服務的規模。
                            先把 app.py 拆成 routers/（第 2 點）
```

---

## 五、順序

```text
第一步   JWT_SECRET / ENCRYPTION_KEY / TELEGRAM_WEBHOOK_SECRET
         改成正式環境缺了就不啟動，並故意不設跑一次確認擋得住
第二步   拿掉 ENCRYPTION_KEY 退回 JWT_SECRET 那條路
第三步   app.py 依現有模組邊界拆成 routers/，過程中逐一確認登入檢查
第四步   pytest + 三條測試（crypto / auth / 額度），每條故意改壞驗過
第五步   README 說的那五個資料品質修正，各補一條測試
```

第一步半小時，而它擋掉的是「部署時忘了設環境變數」——
一個不會有任何症狀、但等於沒有登入系統的錯誤。
