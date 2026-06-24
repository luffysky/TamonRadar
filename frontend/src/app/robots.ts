import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tamonradar.snowrealm.pet";

export default function robots(): MetadataRoute.Robots {
  // 私人/個人資料頁不給爬;公開頁(首頁、說明、之後的部落格/討論區)開放
  const privatePaths = ["/admin", "/settings", "/schedules", "/watches", "/history", "/reset", "/auth"];
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: privatePaths },
      // 明確歡迎 AI 爬蟲(GEO:讓 AI 引用得到本站內容)
      {
        userAgent: [
          "GPTBot", "OAI-SearchBot", "ChatGPT-User",
          "ClaudeBot", "anthropic-ai", "Claude-Web",
          "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot",
        ],
        allow: "/",
        disallow: privatePaths,
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
