import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { API_BASE, type BlogPost } from "@/lib/api";
import RichContent from "@/components/social/RichContent";
import PostInteractions from "@/components/PostInteractions";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tamonradar.snowrealm.pet";

async function getPost(slug: string): Promise<BlogPost | null> {
  try {
    const res = await fetch(`${API_BASE}/api/blog/${slug}`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const post = await getPost(params.slug);
  if (!post) return { title: "找不到文章" };
  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      type: "article",
      title: post.title,
      description: post.excerpt,
      images: post.cover_image ? [post.cover_image] : undefined,
      url: `${SITE}/blog/${post.slug}`,
    },
  };
}

function buildToc(html: string): { toc: { id: string; text: string; level: number }[]; withIds: string } {
  const toc: { id: string; text: string; level: number }[] = [];
  let i = 0;
  const withIds = (html || "").replace(/<(h[23])([^>]*)>([\s\S]*?)<\/\1>/gi, (_m, tag, attrs, inner) => {
    const text = inner.replace(/<[^>]+>/g, "").trim();
    if (!text) return `<${tag}${attrs}>${inner}</${tag}>`;
    const id = `sec-${i++}`;
    toc.push({ id, text, level: tag.toLowerCase() === "h2" ? 2 : 3 });
    return `<${tag}${attrs} id="${id}">${inner}</${tag}>`;
  });
  return { toc, withIds };
}

function readingMinutes(html: string): number {
  const text = (html || "").replace(/<[^>]+>/g, "");
  return Math.max(1, Math.ceil(text.length / 400));
}

export default async function ArticlePage({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);
  if (!post) notFound();

  const { toc, withIds } = buildToc(post.content ?? "");
  const minutes = readingMinutes(post.content ?? "");

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    image: post.cover_image || undefined,
    datePublished: post.created_at,
    dateModified: post.updated_at,
    author: { "@type": "Organization", name: "TamonRadar" },
    mainEntityOfPage: `${SITE}/blog/${post.slug}`,
  };

  return (
    <article className="mx-auto max-w-3xl">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Link href="/blog" className="text-sm text-brand-600 hover:underline dark:text-brand-300">← 回部落格</Link>
      {post.category && (
        <span className="mt-3 inline-block rounded-full bg-brand-100 px-2 py-0.5 text-xs text-brand-700">{post.category}</span>
      )}
      <h1 className="mt-2 text-3xl font-bold text-slate-800 dark:text-slate-100">{post.title}</h1>
      <p className="mt-2 text-sm text-slate-400">
        {post.author && post.author_id ? (
          <>作者:<Link href={`/blogs/${post.author_id}`} className="text-brand-600 hover:underline dark:text-brand-300">{post.author}</Link> · </>
        ) : null}
        {post.created_at ? new Date(post.created_at).toLocaleDateString("zh-TW") : ""}
        {" · 約 " + minutes + " 分鐘閱讀"}
      </p>
      {post.cover_image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.cover_image} alt={post.title} className="mt-4 w-full rounded-xl object-cover" />
      )}

      {toc.length >= 2 && (
        <nav className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-700 dark:bg-slate-800/50">
          <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">目錄</p>
          <ul className="space-y-1">
            {toc.map((t) => (
              <li key={t.id} className={t.level === 3 ? "ml-4" : ""}>
                <a href={`#${t.id}`} className="text-slate-600 hover:text-brand-600 hover:underline dark:text-slate-300">{t.text}</a>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <div className="mt-6 scroll-mt-20">
        <RichContent html={withIds} />
      </div>

      {post.tags && post.tags.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-1.5">
          {post.tags.map((t) => (
            <Link key={t} href={`/blog?tag=${encodeURIComponent(t)}`} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300">#{t}</Link>
          ))}
        </div>
      )}

      <PostInteractions
        postId={post.id}
        slug={post.slug}
        title={post.title}
        coverImage={post.cover_image}
        initialLikes={post.likes ?? 0}
        initialLiked={post.liked ?? false}
        initialComments={post.comments ?? []}
      />
    </article>
  );
}
