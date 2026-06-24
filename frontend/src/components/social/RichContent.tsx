import DOMPurify from "isomorphic-dompurify";

/** 安全渲染富文本 HTML(編輯器產出),套用 .markdown 排版。可在 server/client 使用。 */
export default function RichContent({ html }: { html: string }) {
  const clean = DOMPurify.sanitize(html || "", {
    ADD_ATTR: ["target", "rel"],
  });
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: clean }} />;
}
