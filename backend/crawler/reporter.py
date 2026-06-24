from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")  # 伺服器無畫面,用非互動後端
import matplotlib.pyplot as plt
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# 讓圖表能顯示中文(找不到字型就退回預設,不會壞)
for _font in ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "PingFang TC", "Noto Sans CJK TC"]:
    try:
        matplotlib.rcParams["font.sans-serif"] = [_font]
        matplotlib.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue

COLUMN_ORDER = [
    "keyword", "category", "character", "title", "url", "domain", "snippet", "price",
    "is_listing", "image_url", "key_info", "page_title", "meta_description", "h1",
    "google_page", "status", "error",
]


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    """把爬蟲結果轉成欄位齊全、排序固定的 DataFrame。

    修正:即使 records 為空(全被擋),也補齊所有欄位,後面 df["category"] 不會 KeyError。
    """
    df = pd.DataFrame(records)
    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    existing = [c for c in COLUMN_ORDER if c in df.columns]
    remaining = [c for c in df.columns if c not in existing]
    df = df[existing + remaining]
    # 缺值會變 NaN,而 Postgres 的 JSON 欄位不接受 NaN(存檔會炸)→ 全部清成空字串
    return df.where(pd.notnull(df), "")


def ensure_output_dirs(output_dir: str) -> tuple[Path, Path]:
    out = Path(output_dir)
    charts = out / "charts"
    out.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)
    return out, charts


def save_csv(df: pd.DataFrame, output_dir: str, name: str = "tammon_results.csv") -> Path:
    out, _ = ensure_output_dirs(output_dir)
    path = out / name
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_excel(df: pd.DataFrame, output_dir: str, name: str = "tammon_results.xlsx") -> Path:
    out, _ = ensure_output_dirs(output_dir)
    path = out / name

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="raw_data")

        if "category" in df.columns and not df.empty:
            category_summary = df["category"].fillna("未分類").value_counts().reset_index()
            category_summary.columns = ["category", "count"]
            category_summary.to_excel(writer, index=False, sheet_name="category_summary")

        if "domain" in df.columns and not df.empty:
            domain_summary = df["domain"].fillna("unknown").value_counts().reset_index().head(30)
            domain_summary.columns = ["domain", "count"]
            domain_summary.to_excel(writer, index=False, sheet_name="domain_summary")

    beautify_excel(path)
    return path


def beautify_excel(path: Path) -> None:
    wb = load_workbook(path)

    for ws in wb.worksheets:
        ws.freeze_panes = "A2"

        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2F5597")
            cell.alignment = Alignment(horizontal="center")

        for column_cells in ws.columns:
            max_length = 12
            col_letter = get_column_letter(column_cells[0].column)
            for cell in column_cells:
                value = str(cell.value) if cell.value is not None else ""
                max_length = max(max_length, min(len(value) + 2, 60))
            ws.column_dimensions[col_letter].width = max_length

        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

    wb.save(path)


def save_charts(df: pd.DataFrame, output_dir: str) -> list[Path]:
    _, charts = ensure_output_dirs(output_dir)
    chart_paths: list[Path] = []

    if df.empty:
        return chart_paths

    if "category" in df.columns:
        category_count = df["category"].fillna("未分類").value_counts()
        if not category_count.empty:
            plt.figure(figsize=(10, 6))
            category_count.plot(kind="bar", color="#2F5597")
            plt.title("多聞資訊分類統計")
            plt.xlabel("分類")
            plt.ylabel("數量")
            plt.tight_layout()
            path = charts / "category_count.png"
            plt.savefig(path, dpi=180)
            plt.close()
            chart_paths.append(path)

    if "domain" in df.columns:
        domain_count = df["domain"].fillna("unknown").value_counts().head(10)
        if not domain_count.empty:
            plt.figure(figsize=(10, 6))
            domain_count.plot(kind="bar", color="#4472C4")
            plt.title("來源網站 Top 10")
            plt.xlabel("網站")
            plt.ylabel("數量")
            plt.tight_layout()
            path = charts / "domain_count.png"
            plt.savefig(path, dpi=180)
            plt.close()
            chart_paths.append(path)

    return chart_paths


def build_summary(df: pd.DataFrame) -> dict:
    """給前端用的統計摘要(JSON 可序列化)。"""
    if df.empty:
        return {
            "total": 0,
            "with_price": 0,
            "categories": {},
            "domains": {},
        }
    categories = df["category"].fillna("未分類").value_counts().to_dict() if "category" in df else {}
    domains = df["domain"].fillna("unknown").value_counts().head(10).to_dict() if "domain" in df else {}
    with_price = int((df["price"].fillna("") != "").sum()) if "price" in df else 0
    return {
        "total": int(len(df)),
        "with_price": with_price,
        "categories": {str(k): int(v) for k, v in categories.items()},
        "domains": {str(k): int(v) for k, v in domains.items()},
    }


def save_markdown_report(df: pd.DataFrame, output_dir: str, name: str = "report.md") -> Path:
    out, _ = ensure_output_dirs(output_dir)
    path = out / name

    total = len(df)
    lines = ["# TamonRadar 多聞情報報告", "", f"總資料筆數:{total}", ""]

    if df.empty:
        lines.append("這次沒有取得任何資料(可能被攔截或關鍵字無結果)。")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    category_summary = df["category"].fillna("未分類").value_counts()
    domain_summary = df["domain"].fillna("unknown").value_counts().head(10)
    price_df = df[df["price"].fillna("") != ""].copy()
    merch_df = df[df["category"] == "周邊/商品"].copy()

    lines += ["## 分類統計", ""]
    for category, count in category_summary.items():
        lines.append(f"- {category}: {count}")

    lines += ["", "## 來源網站 Top 10", ""]
    for domain, count in domain_summary.items():
        lines.append(f"- {domain}: {count}")

    lines += ["", "## 有偵測到價格的資料", ""]
    if price_df.empty:
        lines.append("目前沒有偵測到明確價格。")
    else:
        for _, row in price_df.head(20).iterrows():
            lines.append(f"- {row.get('title', '')} / {row.get('price', '')} / {row.get('url', '')}")

    lines += ["", "## 周邊/商品候選清單", ""]
    if merch_df.empty:
        lines.append("目前沒有分類為周邊/商品的資料。")
    else:
        for _, row in merch_df.head(30).iterrows():
            lines += [
                f"### {row.get('title', '')}",
                f"- 網址:{row.get('url', '')}",
                f"- 價格:{row.get('price', '') or '未偵測'}",
                f"- 摘要:{row.get('key_info', '')}",
                "",
            ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
