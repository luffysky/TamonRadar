import { BAR_COLORS } from "@/lib/format";

export default function BarChart({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data ?? {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-400">沒有資料</p>
      ) : (
        <div className="space-y-2">
          {entries.map(([label, value], i) => (
            <div key={label} className="flex items-center gap-2">
              <div className="w-28 shrink-0 truncate text-right text-xs text-slate-600" title={label}>
                {label}
              </div>
              <div className="h-5 flex-1 rounded bg-slate-100">
                <div
                  className="flex h-5 items-center justify-end rounded px-2 text-[10px] font-medium text-white"
                  style={{
                    width: `${Math.max(8, (value / max) * 100)}%`,
                    backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
                  }}
                >
                  {value}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
