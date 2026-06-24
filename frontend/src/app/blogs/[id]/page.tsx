import type { Metadata } from "next";
import Link from "next/link";
import { Radar, User } from "lucide-react";
import type { BlogPost } from "@/lib/api";
import SubscribeButton from "@/components/SubscribeButton";

const API = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");

interface AuthorBlog { author_id: number; author: string; post_count: number; series: string[]; posts: BlogPost[]; }

async function fetchAuthor(id: string): Promise<AuthorBlog | null> {
  try {
    const res = await fetch(`${API}/api/blog/author/${id}`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const d = await fetchAuthor(params.id);
  if (!d) return { title: "作者部落格 | TamonRadar" };
  return {
    title: `${d.author} 的部落格 | TamonRadar`,
    description: `${d.author} 在 TamonRadar 的文章(共 ${d.post_count} 篇)。`,
  };
}

export default async function AuthorBlogPage({ params }: { params: { id: string } }) {
  const d = await fetchAuthor(params.id);
  if (!d) {
    return (
      <div className="py-20 text-center">
        <p className="text-sm text-rose-500">找不到這個作者。</p>
        <Link href="/blog" className="mt-3 inline-block text-sm text-brand-600 hover:underline">回部落格</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-gradient-to-br from-brand-600 to-brand-500 p-6 text-white shadow">
        <div className="flex flex-wrap items-center gap-4">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-white/20"><User className="h-8 w-8" /></span>
          <div className="flex-1">
            <h1 className="text-2xl font-bold">{d.author} 的部落格</h1>
            <p className="text-sm text-brand-50">共 {d.post_count} 篇文章{d.series?.length ? ` · ${d.series.length} 個系列` : ""}</p>
          </div>
          <SubscribeButton authorId={d.author_id} />
        </div>
        {d.series?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {d.series.map((s) => (
              <span key={s} className="rounded-full bg-white/20 px-2.5 py-1 text-xs">📚 {s}</span>
            ))}
          </div>
        )}
      </section>

      {d.posts.length === 0 ? (
        <p className="text-sm text-slate-400">這位作者還沒有公開文章。</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {d.posts.map((p) => (
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
                <p className="mt-2 text-xs text-slate-400">{p.created_at ? new Date(p.created_at).toLocaleDateString("zh-TW") : ""}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
