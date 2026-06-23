# n8n 自動化延伸流程

這個 Python 專案跑完後，可以接 n8n 做成每日情報系統。

## 流程

Cron 每天早上 9 點
↓
Execute Command: python main.py
↓
Read Binary File: output/tammon_results.xlsx
↓
Send Email: 附上 Excel 與 report.md
↓
LINE Notify / Discord / Slack 推送摘要

## 可以推送的摘要

今日多聞情報更新：

- 新增搜尋資料：xx 筆
- 周邊/商品：xx 筆
- 有價格資料：xx 筆
- 最常出現來源網站：xxx
- 值得關注商品：xxx

## 下一階段

可以接 OpenAI / Gemini API，讓 AI 自動判斷：

- 哪些是真正商品頁
- 哪些是重複資訊
- 哪些值得購買
- 哪些是舊資料
- 哪些有預購/再販可能
