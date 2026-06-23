import type { ProgressEvent } from "@/lib/types";

const TYPE_STYLE: Record<string, string> = {
  blocked: "text-amber-600",
  error: "text-rose-600",
  warning: "text-amber-600",
  done: "text-emerald-600",
  stopped: "text-slate-500 dark:text-slate-400",
};

export default function ProgressPanel({
  events,
  running,
}: {
  events: ProgressEvent[];
  running: boolean;
}) {
  const last = events[events.length - 1];
  const detail = [...events].reverse().find((e) => e.type === "detail_progress");
  const pct =
    detail && detail.total ? Math.round(((detail.current ?? 0) / detail.total) * 100) : null;

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        {running && (
          <span className="h-3 w-3 animate-pulse rounded-full bg-brand-500" aria-hidden />
        )}
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          {running ? "爬取中…" : "進度紀錄"}
        </span>
        {last?.message ? <span className="text-xs text-slate-400">· {last.message}</span> : null}
      </div>

      {pct !== null && (
        <div className="mb-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
            <div className="h-2 rounded-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-1 text-right text-xs text-slate-400">
            詳細頁 {detail?.current}/{detail?.total}
          </div>
        </div>
      )}

      <div className="scroll-thin max-h-48 space-y-1 overflow-auto text-xs">
        {events.map((e, i) => (
          <div key={i} className={`flex gap-2 ${TYPE_STYLE[e.type] ?? "text-slate-500 dark:text-slate-400"}`}>
            <span className="text-slate-300">{String(i + 1).padStart(2, "0")}</span>
            <span>{e.message ?? e.type}</span>
          </div>
        ))}
        {events.length === 0 && <p className="text-slate-400">等待開始…</p>}
      </div>
    </div>
  );
}
