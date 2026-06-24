// 後台祕密路徑前綴(可用 NEXT_PUBLIC_ADMIN_SLUG 覆寫;改了要同步 middleware 的環境變數)
export const ADMIN_SLUG = process.env.NEXT_PUBLIC_ADMIN_SLUG || "console-x7k2";
export const ADMIN_BASE = `/${ADMIN_SLUG}`;
