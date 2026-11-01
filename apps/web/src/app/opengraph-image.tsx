import { ImageResponse } from "next/og";

// Text and lines only: the project uses no club crest, logo, or player photo.
// The image uses the built-in font, so the build fetches no font.
export const alt =
  "Highbury: an AI football analyst for Arsenal's 2003-04 and 2025-26 seasons. Every number checked.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The colors of globals.css. The image cannot read CSS variables.
const BACKGROUND = "#0A120E";
const FOREGROUND = "#F1EEE6";
const MUTED = "#A3ADA7";
const PRIMARY = "#C8202B";
const VERIFIED = "#9BEBC2";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: BACKGROUND,
          color: FOREGROUND,
          borderLeft: `16px solid ${PRIMARY}`,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <div style={{ fontSize: 112, fontWeight: 700, letterSpacing: -2 }}>Highbury</div>
          <div style={{ fontSize: 44, lineHeight: 1.25, maxWidth: 960 }}>
            An AI football analyst for Arsenal&apos;s 2003-04 Invincibles and the 2025-26 side.
          </div>
          <div style={{ fontSize: 40, color: VERIFIED }}>Every number checked.</div>
        </div>
        <div style={{ fontSize: 26, color: MUTED }}>
          Unofficial fan project. Not affiliated with Arsenal FC or the Premier League.
        </div>
      </div>
    ),
    size,
  );
}
