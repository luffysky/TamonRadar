import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// 後台藏在祕密路徑;直接打 /admin 會被導走。實際資料權限仍由後端 API(get_admin)把關。
const SLUG = process.env.NEXT_PUBLIC_ADMIN_SLUG || "console-x7k2";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // 祕密路徑 → 內部 /admin
  if (pathname === `/${SLUG}` || pathname.startsWith(`/${SLUG}/`)) {
    const url = req.nextUrl.clone();
    url.pathname = "/admin" + pathname.slice(`/${SLUG}`.length);
    return NextResponse.rewrite(url);
  }

  // 直接打內部 /admin → 導回首頁(藏起來)
  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.png|apple-icon.png|manifest.webmanifest|robots.txt|sitemap.xml|llms.txt|sw.js|logo-mark.png).*)"],
};
