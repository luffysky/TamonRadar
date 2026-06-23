export const CATEGORY_COLORS: Record<string, string> = {
  "周邊/商品": "bg-rose-100 text-rose-700 border-rose-200",
  "購物頁": "bg-amber-100 text-amber-700 border-amber-200",
  "角色資訊": "bg-violet-100 text-violet-700 border-violet-200",
  "動畫/漫畫": "bg-sky-100 text-sky-700 border-sky-200",
  "討論/心得": "bg-emerald-100 text-emerald-700 border-emerald-200",
  "其他": "bg-slate-100 text-slate-600 border-slate-200",
};

export function categoryClass(category: string): string {
  return CATEGORY_COLORS[category] ?? CATEGORY_COLORS["其他"];
}

export const BAR_COLORS = [
  "#2f5597", "#3b6fe0", "#5b8def", "#f59e0b", "#10b981", "#8b5cf6", "#ef4444", "#0ea5e9",
];
