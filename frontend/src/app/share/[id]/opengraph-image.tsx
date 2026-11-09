import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");

export default async function Image({ params: paramsPromise }: { params: Promise<{ id: string }> }) {
  const params = await paramsPromise;
  let kw = "搜尋結果";
  let total = 0;
  try {
    const res = await fetch(`${API}/api/share/${params.id}`);
    if (res.ok) {
      const d = await res.json();
      kw = (d.keywords || []).join("、") || kw;
      total = d.summary?.total ?? (d.records?.length ?? 0);
    }
  } catch { /* ignore */ }

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", flexDirection: "column",
          justifyContent: "center", padding: "80px",
          background: "linear-gradient(135deg, #2f5597 0%, #4a76c4 100%)", color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 40, opacity: 0.85, display: "flex", alignItems: "center" }}>📡 TamonRadar 多聞情報雷達</div>
        <div style={{ fontSize: 88, fontWeight: 800, marginTop: 30, lineHeight: 1.1 }}>{kw.slice(0, 28)}</div>
        <div style={{ fontSize: 44, marginTop: 30, opacity: 0.9 }}>共 {total} 筆比價結果 · 點開查看</div>
      </div>
    ),
    size,
  );
}
