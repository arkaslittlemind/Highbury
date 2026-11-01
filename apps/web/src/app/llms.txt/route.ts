import { renderLlmsTxt } from "@/lib/ai-readable";

export function GET() {
  return new Response(renderLlmsTxt(), {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=86400, stale-while-revalidate=604800",
    },
  });
}
