/** @type {import('next').NextConfig} */
const nextConfig = {
  // 商品圖來自各種外站,全站用一般 <img> 直接顯示,不經過 next/image;
  // 不開 remotePatterns 萬用字元,否則 /_next/image 會變成任何人都能用的開放圖片代理。
};

export default nextConfig;
