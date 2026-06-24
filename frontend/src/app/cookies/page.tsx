import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Cookie 政策",
  description: "TamonRadar 如何使用 Cookie 與本機儲存。",
};

export default function CookiesPage() {
  return (
    <article className="markdown mx-auto max-w-3xl">
      <h1>Cookie 政策</h1>
      <p>最後更新:2026 年</p>
      <p>本頁說明 TamonRadar 如何使用 Cookie 與瀏覽器本機儲存(localStorage)。</p>

      <h2>一、我們使用的類型</h2>
      <ul>
        <li><strong>必要性</strong>:維持你的登入狀態(儲存登入權杖)、記住深色模式與是否已看過提示。沒有這些網站無法正常運作。</li>
        <li><strong>功能性</strong>:記住你的偏好設定(例如搜尋來源、是否同意 Cookie)。</li>
      </ul>
      <p>目前本服務<strong>不使用</strong>第三方廣告或追蹤 Cookie。</p>

      <h2>二、如何管理</h2>
      <p>
        你可以在瀏覽器設定中清除或封鎖 Cookie / 本機儲存,但這可能導致無法登入或部分功能異常。
      </p>

      <h2>三、變更</h2>
      <p>若我們調整 Cookie 使用方式,會更新本頁。</p>

      <p className="text-sm text-slate-400">※ 本頁為一般範本,正式上線前請依實際使用情況調整。</p>
    </article>
  );
}
