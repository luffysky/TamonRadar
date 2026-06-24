"use client";

import { useRef } from "react";

/** 讓橫向捲動容器可用滑鼠拖曳捲動,同時不影響點擊(拖了才擋 click)。 */
export function useDragScroll() {
  const ref = useRef<HTMLDivElement>(null);
  const st = useRef({ down: false, startX: 0, scroll: 0, moved: false });

  return {
    ref,
    style: { cursor: "grab" as const },
    onPointerDown: (e: React.PointerEvent) => {
      const el = ref.current;
      if (!el) return;
      st.current = { down: true, startX: e.pageX, scroll: el.scrollLeft, moved: false };
    },
    onPointerMove: (e: React.PointerEvent) => {
      const el = ref.current;
      const s = st.current;
      if (!s.down || !el) return;
      const dx = e.pageX - s.startX;
      if (Math.abs(dx) > 4) s.moved = true;
      el.scrollLeft = s.scroll - dx;
    },
    onPointerUp: () => { st.current.down = false; },
    onPointerLeave: () => { st.current.down = false; },
    onClickCapture: (e: React.MouseEvent) => {
      if (st.current.moved) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
  };
}
