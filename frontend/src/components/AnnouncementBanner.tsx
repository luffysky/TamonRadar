"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { getAnnouncements, type Announcement } from "@/lib/api";

const BG: Record<string, string> = {
  info: "bg-brand-600",
  warning: "bg-amber-500",
  success: "bg-emerald-600",
};

export default function AnnouncementBanner() {
  const [anns, setAnns] = useState<Announcement[]>([]);
  const [off, setOff] = useState(false);

  useEffect(() => {
    getAnnouncements().then((d) => setAnns(d.announcements)).catch(() => {});
    try { setOff(localStorage.getItem("tr_ann_off") === "1"); } catch { /* ignore */ }
  }, []);

  if (off || anns.length === 0) return null;

  const bg = BG[anns[0].level] || BG.info;
  const text = anns.map((a) => `📢 ${a.title}${a.body ? " — " + a.body : ""}`).join("　　•　　");

  function close() {
    setOff(true);
    try { localStorage.setItem("tr_ann_off", "1"); } catch { /* ignore */ }
  }

  return (
    <div className={`relative flex items-center ${bg} text-white`}>
      <div className="flex-1 overflow-hidden">
        <div className="animate-marquee whitespace-nowrap py-1.5 text-sm font-medium">
          <span className="mx-4">{text}</span>
          <span className="mx-4">{text}</span>
        </div>
      </div>
      <button onClick={close} aria-label="關閉公告" className="shrink-0 px-3 opacity-80 hover:opacity-100">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
