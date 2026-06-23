from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def ensure_output_dirs(output_dir: str) -> tuple[Path, Path]:
    out = Path(output_dir)
    charts = out / "charts"
    out.mkdir(exist_ok=True)
    charts.mkdir(exist_ok=True)
    return out, charts


def save_csv(df: pd.DataFrame, output_dir: str) -> Path:
    out, _ = ensure_output_dirs(output_dir)
    path = out / "tammon_results.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_excel(df: pd.DataFrame, output_dir: str) -> Path:
    out, _ = ensure_output_dirs(output_dir)
    path = out / "tammon_results.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="raw_data")

        category_summary = df["category"].value_counts().reset_index()
        category_summary.columns = ["category", "count"]
        category_summary.to_excel(writer, index=False, sheet_name="category_summary")

        domain_summary = df["domain"].value_counts().reset_index().head(30)
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
    chart_paths = []

    if "category" in df.columns and not df.empty:
        category_count = df["category"].fillna("未分類").value_counts()
        plt.figure(figsize=(10, 6))
        category_count.plot(kind="bar")
        plt.title("多聞資訊分類統計")
        plt.xlabel("分類")
        plt.ylabel("數量")
        plt.tight_layout()
        path = charts / "category_count.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

    if "domain" in df.columns and not df.empty:
        domain_count = df["domain"].fillna("unknown").value_counts().head(10)
        plt.figure(figsize=(10, 6))
        domain_count.plot(kind="bar")
        plt.title("來源網站 Top 10")
        plt.xlabel("網站")
        plt.ylabel("數量")
        plt.tight_layout()
        path = charts / "domain_count.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_paths.append(path)

    if "price" in df.columns and not df.empty:
        price_df = df[df["price"].fillna("") != ""]
        price_count = price_df["category"].fillna("未分類").value_counts()
        if not price_count.empty:
            plt.figure(figsize=(10, 6))
            price_count.plot(kind="bar")
            plt.title("有偵測到價格的資料分類")
            plt.xlabel("分類")
            plt.ylabel("數量")
            plt.tight_layout()
            path = charts / "price_distribution.png"
            plt.savefig(path, dpi=180)
            plt.close()
            chart_paths.append(path)

    return chart_paths


def save_markdown_report(df: pd.DataFrame, output_dir: str) -> Path:
    out, _ = ensure_output_dirs(output_dir)
    path = out / "report.md"

    total = len(df)
    category_summary = df["category"].fillna("未分類").value_counts()
    domain_summary = df["domain"].fillna("unknown").value_counts().head(10)

    merch_df = df[df["category"] == "周邊/商品"].copy()
    price_df = df[df["price"].fillna("") != ""].copy()

    lines = []
    lines.append("# 多聞情報系統報告")
    lines.append("")
    lines.append(f"總資料筆數：{total}")
    lines.append("")
    lines.append("## 分類統計")
    lines.append("")
    for category, count in category_summary.items():
        lines.append(f"- {category}: {count}")

    lines.append("")
    lines.append("## 來源網站 Top 10")
    lines.append("")
    for domain, count in domain_summary.items():
        lines.append(f"- {domain}: {count}")

    lines.append("")
    lines.append("## 有偵測到價格的資料")
    lines.append("")
    if price_df.empty:
        lines.append("目前沒有偵測到明確價格。")
    else:
        for _, row in price_df.head(20).iterrows():
            lines.append(f"- {row.get('title', '')} / {row.get('price', '')} / {row.get('url', '')}")

    lines.append("")
    lines.append("## 周邊/商品候選清單")
    lines.append("")
    if merch_df.empty:
        lines.append("目前沒有分類為周邊/商品的資料。")
    else:
        for _, row in merch_df.head(30).iterrows():
            lines.append(f"### {row.get('title', '')}")
            lines.append(f"- 網址：{row.get('url', '')}")
            lines.append(f"- 價格：{row.get('price', '') or '未偵測'}")
            lines.append(f"- 摘要：{row.get('key_info', '')}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
