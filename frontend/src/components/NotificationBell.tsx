"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { useAuth } from "./AuthProvider";
import { getNotifications, markNotificationsRead, type Notif } from "@/lib/api";

export default function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  async function load() {
    const d = await getNotifications();
    setItems(d.items);
    setUnread(d.unread);
  }

  useEffect(() => {
    if (!user) return;
    load();
    const t = setInterval(load, 60000); // 每分鐘更新一次
    return () => clearInterval(t);
  }, [user]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  if (!user) return null;

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      await markNotificationsRead();
      setUnread(0);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} aria-label="通知" className="relative grid h-9 w-9 place-items-center rounded-md text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">{unread > 9 ? "9+" : unread}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 max-h-[70vh] w-80 max-w-[calc(100vw-1.5rem)] overflow-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl dark:border-slate-700 dark:bg-slate-800">
          <p className="px-3 py-2 text-sm font-semibold text-slate-700 dark:text-slate-200">通知</p>
          {items.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-slate-400">目前沒有通知</p>
          ) : items.map((n) => {
            const inner = (
              <>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{n.title}</p>
                {n.body && <p className="mt-0.5 whitespace-pre-wrap text-xs text-slate-500 dark:text-slate-400">{n.body.slice(0, 200)}</p>}
                <p className="mt-1 text-[10px] text-slate-400">{n.created_at ? new Date(n.created_at).toLocaleString("zh-TW") : ""}</p>
              </>
            );
            return n.url ? (
              <a key={n.id} href={n.url} target="_blank" rel="noreferrer" className="block rounded-lg px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-700">{inner}</a>
            ) : (
              <div key={n.id} className="rounded-lg px-3 py-2">{inner}</div>
            );
          })}
        </div>
      )}
    </div>
  );
}
