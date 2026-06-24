import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { API_BASE, type BlogPost } from "@/lib/api";
import RichContent from "@/components/social/RichContent";

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

export default async function ArticlePage({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);
  if (!post) notFound();

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
      </p>
      {post.cover_image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.cover_image} alt={post.title} className="mt-4 w-full rounded-xl object-cover" />
      )}
      <div className="mt-6">
        <RichContent html={post.content ?? ""} />
      </div>
    </article>
  );
}
