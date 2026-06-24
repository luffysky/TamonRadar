import type { Metadata } from "next";

const API = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");

/** 讀後台設定的各頁 SEO,沒設就用 fallback。供 server 元件的 generateMetadata 使用。 */
export async function pageMeta(path: string, fallback: Metadata): Promise<Metadata> {
  try {
    const res = await fetch(`${API}/api/seo/page?path=${encodeURIComponent(path)}`, { next: { revalidate: 120 } });
    if (!res.ok) return fallback;
    const d = await res.json();
    if (!d?.title && !d?.description && !d?.keywords) return fallback;
    return {
      title: d.title || fallback.title,
      description: d.description || fallback.description,
      keywords: d.keywords || undefined,
    };
  } catch {
    return fallback;
  }
}
