import type { Metadata } from "next";
import ShareView from "@/components/ShareView";

const API = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "").replace(/\/+$/, "");

async function fetchShared(id: string) {
  try {
    const res = await fetch(`${API}/api/share/${id}`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params: paramsPromise }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const params = await paramsPromise;
  const data = await fetchShared(params.id);
  if (!data) return { title: "分享的搜尋結果 | TamonRadar" };
  const kw = (data.keywords || []).join("、") || "搜尋結果";
  const total = data.summary?.total ?? (data.records?.length ?? 0);
  const title = `${kw} — TamonRadar 搜尋結果`;
  const description = `共 ${total} 筆比價結果,在 TamonRadar 查看。`;
  const ogImage = `${SITE}/share/${params.id}/opengraph-image`;
  return {
    title,
    description,
    openGraph: { title, description, images: [ogImage], type: "website" },
    twitter: { card: "summary_large_image", title, description, images: [ogImage] },
  };
}

export default async function SharePage({ params: paramsPromise }: { params: Promise<{ id: string }> }) {
  const params = await paramsPromise;
  return <ShareView id={params.id} />;
}
