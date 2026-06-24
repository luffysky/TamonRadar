"use client";

import { useState } from "react";

/** 商品圖:沒圖或載入失敗時,顯示品牌吉祥物佔位圖,不破圖。填滿父容器。 */
export default function ProductImage({ src, alt = "" }: { src?: string; alt?: string }) {
  const [err, setErr] = useState(false);

  if (!src || err) {
    return (
      <div className="grid h-full w-full place-items-center bg-gradient-to-br from-brand-50 to-slate-100 dark:from-slate-700 dark:to-slate-800">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-mark.png" alt="" className="h-1/2 w-1/2 object-contain opacity-40 grayscale-[20%]" />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setErr(true)}
      className="h-full w-full object-cover transition group-hover:scale-105"
    />
  );
}
