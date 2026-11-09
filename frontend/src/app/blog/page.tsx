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

async function getPosts(qs: string): Promise<BlogPost[]> {
  try {
    const res = await fetch(`${API_BASE}/api/blog${qs}`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    return (await res.json()).posts;
  } catch {
    return [];
  }
}

async function getTaxonomy(): Promise<{ categories: { name: string; count: number }[]; tags: { name: string; count: number }[] }> {
  try {
    const res = await fetch(`${API_BASE}/api/blog-taxonomy`, { next: { revalidate: 60 } });
    if (!res.ok) return { categories: [], tags: [] };
    return res.json();
  } catch {
    return { categories: [], tags: [] };
  }
}

const PER = 12;

export default async function BlogPage({ searchParams: searchParamsPromise }: { searchParams?: Promise<{ page?: string; category?: string; tag?: string }> }) {
  const searchParams = await searchParamsPromise;
  const category = searchParams?.category || "";
  const tag = searchParams?.tag || "";
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (tag) params.set("tag", tag);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const [all, tax] = await Promise.all([getPosts(qs), getTaxonomy()]);
  const filtering = Boolean(category || tag);
  const featured = !filtering ? all.filter((p) => p.featured).slice(0, 3) : [];
  const pageCount = Math.max(1, Math.ceil(all.length / PER));
  const page = Math.min(Math.max(1, Number(searchParams?.page) || 1), pageCount);
  const posts = all.slice((page - 1) * PER, page * PER);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">部落格</h1>
        <BlogActions />
      </div>

      {(tax.categories.length > 0 || tax.tags.length > 0) && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <Link href="/blog" className={`rounded-full px-2.5 py-1 ${!filtering ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300"}`}>全部</Link>
            {tax.categories.map((c) => (
              <Link key={c.name} href={`/blog?category=${encodeURIComponent(c.name)}`} className={`rounded-full px-2.5 py-1 ${category === c.name ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300"}`}>{c.name} ({c.count})</Link>
            ))}
          </div>
          {tax.tags.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              {tax.tags.slice(0, 20).map((t) => (
                <Link key={t.name} href={`/blog?tag=${encodeURIComponent(t.name)}`} className={`rounded-full px-2 py-0.5 ${tag === t.name ? "bg-brand-600 text-white" : "bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400"}`}>#{t.name}</Link>
              ))}
            </div>
          )}
        </div>
      )}

      {filtering && <p className="text-sm text-slate-500 dark:text-slate-400">篩選:{category || `#${tag}`} · {all.length} 篇</p>}

      {featured.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-amber-600 dark:text-amber-400">★ 精選文章</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {featured.map((p) => (
              <Link key={p.id} href={`/blog/${p.slug}`} className="card overflow-hidden ring-1 ring-amber-200 transition hover:-translate-y-0.5 hover:shadow-lg dark:ring-amber-900">
                {p.cover_image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.cover_image} alt={p.title} className="h-32 w-full object-cover" />
                ) : (
                  <div className="grid h-32 place-items-center bg-gradient-to-br from-amber-500 to-brand-600 text-white"><Radar className="h-9 w-9 opacity-80" /></div>
                )}
                <div className="p-3">
                  <h3 className="line-clamp-2 text-sm font-semibold text-slate-800 dark:text-slate-100">{p.title}</h3>
                  <p className="mt-1 text-[11px] text-slate-400">♥ {p.likes ?? 0}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {all.length === 0 ? (
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
                <p className="mt-2 text-xs text-slate-400">{p.author ? `${p.author} · ` : ""}{p.created_at ? new Date(p.created_at).toLocaleDateString("zh-TW") : ""}{(p.likes ?? 0) > 0 ? ` · ♥ ${p.likes}` : ""}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
      {pageCount > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          {page > 1 ? <Link href={`/blog?${params.toString()}${params.toString() ? "&" : ""}page=${page - 1}`} className="rounded-lg border border-slate-300 px-3 py-1.5 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">← 上一頁</Link> : <span className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-300">← 上一頁</span>}
          <span className="text-slate-500 dark:text-slate-400">{page} / {pageCount}</span>
          {page < pageCount ? <Link href={`/blog?${params.toString()}${params.toString() ? "&" : ""}page=${page + 1}`} className="rounded-lg border border-slate-300 px-3 py-1.5 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-700">下一頁 →</Link> : <span className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-300">下一頁 →</span>}
        </div>
      )}
    </div>
  );
}
