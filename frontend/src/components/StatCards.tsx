import type { Summary } from "@/lib/types";

function Card({ label, value, accent }: { label: string; value: string | number; accent: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent}`}>{value}</div>
    </div>
  );
}

export default function StatCards({ summary }: { summary: Summary }) {
  const topCategory =
    Object.entries(summary.categories ?? {}).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";
  const topDomain =
    Object.entries(summary.domains ?? {}).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Card label="總資料筆數" value={summary.total} accent="text-brand-600" />
      <Card label="偵測到價格" value={summary.with_price} accent="text-rose-600" />
      <Card label="最多分類" value={topCategory} accent="text-violet-600" />
      <Card label="主要來源" value={topDomain} accent="text-emerald-600" />
    </div>
  );
}
