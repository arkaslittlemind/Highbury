import { renderHomeMarkdown } from "@/lib/ai-readable";
import { SITE_URL } from "@/lib/site";

// The Markdown of the home page, for AI agents. The rewrite in next.config.ts
// also serves it at / when a client asks for text/markdown.
export function GET() {
  return new Response(renderHomeMarkdown(), {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Cache-Control": "public, s-maxage=86400, stale-while-revalidate=604800",
      // The HTML page is the one for search results; this is a copy of it.
      "X-Robots-Tag": "noindex, follow",
      Link: `<${SITE_URL}/>; rel="canonical"`,
      Vary: "Accept",
    },
  });
}
