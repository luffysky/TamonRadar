/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    // 商品圖來自各種外站,放寬限制讓 <img> 能直接顯示(教學用途)
    remotePatterns: [{ protocol: "https", hostname: "**" }, { protocol: "http", hostname: "**" }],
  },
};

export default nextConfig;
