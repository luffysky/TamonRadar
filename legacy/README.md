# legacy — 舊版 CLI(僅供參考)

這是 TamonRadar 最初的命令列版本。功能已全部被 `backend/` 取代,而且
`backend/crawler/` 還修好了這個舊版的 5 個資料品質問題(價格、分類、攔截誤判、
URL 副檔名、空資料防呆)。

保留在這裡只是當教學對照,**正式請用 `backend/`**。

獨立執行(可選):

```bash
cd legacy
pip install -r requirements.txt
python main.py
```
