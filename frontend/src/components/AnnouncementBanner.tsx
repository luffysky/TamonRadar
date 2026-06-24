"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { getAnnouncements, type Announcement } from "@/lib/api";

const COLORS: Record<string, string> = {
  info: "bg-brand-50 text-brand-800 border-brand-200 dark:bg-brand-950/40 dark:text-brand-200 dark:border-brand-900",
  warning: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-900",
  success: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:border-emerald-900",
};

export default function AnnouncementBanner() {
  const [anns, setAnns] = useState<Announcement[]>([]);
  const [dismissed, setDismissed] = useState<number[]>([]);

  useEffect(() => {
    getAnnouncements().then((d) => setAnns(d.announcements)).catch(() => {});
    try { setDismissed(JSON.parse(localStorage.getItem("tr_dismissed_ann") || "[]")); } catch { /* ignore */ }
  }, []);

  const visible = anns.filter((a) => !dismissed.includes(a.id));
  if (!visible.length) return null;

  function dismiss(id: number) {
    const n = [...dismissed, id];
    setDismissed(n);
    try { localStorage.setItem("tr_dismissed_ann", JSON.stringify(n)); } catch { /* ignore */ }
  }

  return (
    <div>
      {visible.map((a) => (
        <div key={a.id} className={`flex items-start gap-2 border-b px-4 py-2 text-sm ${COLORS[a.level] || COLORS.info}`}>
          <div className="mx-auto flex max-w-6xl flex-1 gap-2">
            <span><strong>{a.title}</strong> {a.body}</span>
          </div>
          <button onClick={() => dismiss(a.id)} aria-label="關閉" className="opacity-60 hover:opacity-100"><X className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  );
}
