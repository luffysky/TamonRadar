import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "隱私權政策",
  description: "TamonRadar 隱私權政策:我們如何蒐集、使用與保護你的個人資料。",
};

export default function PrivacyPage() {
  return (
    <article className="markdown mx-auto max-w-3xl">
      <h1>隱私權政策</h1>
      <p>最後更新:2026 年</p>
      <p>
        本政策說明 TamonRadar(以下稱「本服務」)如何蒐集、使用與保護你的個人資料。使用本服務即表示你同意本政策。
      </p>

      <h2>一、我們蒐集的資料</h2>
      <ul>
        <li><strong>帳號資料</strong>:你註冊時提供的 email;若使用 Google 登入,則為 Google 提供的 email。</li>
        <li><strong>使用資料</strong>:你的搜尋關鍵字、排程、監看項目、AI 使用次數、發表的文章與回覆。</li>
        <li><strong>你自行填寫的設定</strong>:通知管道(Discord/Telegram)、自備的 AI 金鑰等。</li>
        <li><strong>技術資料</strong>:維持登入所需的 Cookie / 本機儲存。</li>
      </ul>

      <h2>二、我們如何使用</h2>
      <ul>
        <li>提供與維持服務功能(登入、搜尋、通知、社群)。</li>
        <li>依你的設定,將通知送到你指定的 Discord / Telegram。</li>
        <li>改善服務與排除錯誤。</li>
      </ul>

      <h2>三、資料分享</h2>
      <p>
        我們不會販售你的個人資料。僅在下列情況與第三方互動:為了完成你要求的功能(例如呼叫搜尋 API、AI 服務、寄送 email),
        或法律要求時。你自備的金鑰僅用於代你呼叫對應服務。
      </p>

      <h2>四、資料保存與安全</h2>
      <p>密碼以雜湊方式儲存,不以明文保存。我們採取合理措施保護資料,但無法保證網路傳輸絕對安全。</p>

      <h2>五、你的權利</h2>
      <p>你可以查詢、更正或刪除你的帳號資料。如需刪除帳號,請透過下方聯絡方式或站內 AI 助手與我們聯繫。</p>

      <h2>六、聯絡我們</h2>
      <p>如對本政策有任何疑問,歡迎透過網站內的 AI 助手或公告的聯絡方式與我們聯繫。</p>

      <p className="text-sm text-slate-400">
        ※ 本頁為一般範本,正式上線前請依你的實際營運與所在地法規(如台灣個資法、GDPR)調整。
      </p>
    </article>
  );
}
