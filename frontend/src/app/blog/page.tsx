import type { Metadata } from "next";
import Link from "next/link";
import { Radar } from "lucide-react";
import { API_BASE, type BlogPost } from "@/lib/api";
import BlogActions from "@/components/BlogActions";

import { pageMeta } from "@/lib/seo";

export async function generateMetadata(): Promise<Metadata> {
  return pageMeta("/blog", {
    title: "部落格",
    description: "TamonRadar 部落格:搶購攻略、比價技巧、情報整理與站務公告。",
  });
}

async function getPosts(): Promise<BlogPost[]> {
  try {
    const res = await fetch(`${API_BASE}/api/blog`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    return (await res.json()).posts;
  } catch {
    return [];
  }
}

export default async function BlogPage() {
  const posts = await getPosts();
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">部落格</h1>
        <BlogActions />
      </div>
      {posts.length === 0 ? (
        <p className="text-sm text-slate-400">還沒有文章。</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((p) => (
            <Link key={p.id} href={`/blog/${p.slug}`} className="card overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lg">
              {p.cover_image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.cover_image} alt={p.title} className="h-40 w-full object-cover" />
              ) : (
                <div className="grid h-40 place-items-center bg-gradient-to-br from-brand-500 to-brand-700 text-white"><Radar className="h-10 w-10 opacity-80" /></div>
              )}
              <div className="p-4">
                {p.category && <span className="mb-1 inline-block rounded-full bg-brand-100 px-2 py-0.5 text-[10px] text-brand-700">{p.category}</span>}
                <h2 className="line-clamp-2 font-semibold text-slate-800 dark:text-slate-100">{p.title}</h2>
                <p className="mt-1 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">{p.excerpt}</p>
                <p className="mt-2 text-xs text-slate-400">{p.author ? `${p.author} · ` : ""}{p.created_at ? new Date(p.created_at).toLocaleDateString("zh-TW") : ""}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
