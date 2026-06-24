import type { Metadata } from "next";
import ThreadView from "@/components/ThreadView";

const API = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");

async function fetchThread(id: string) {
  try {
    const res = await fetch(`${API}/api/forum/threads/${id}`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const t = await fetchThread(params.id);
  if (!t) return { title: "討論主題 | TamonRadar" };
  const desc = (t.content || "").replace(/<[^>]+>/g, "").slice(0, 100) || `${t.author} 發起的討論`;
  return {
    title: `${t.title} | TamonRadar 討論區`,
    description: desc,
    openGraph: { title: t.title, description: desc, type: "article" },
  };
}

export default function ThreadPage({ params }: { params: { id: string } }) {
  return <ThreadView id={Number(params.id)} />;
}
