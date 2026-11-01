const TURNSTILE_ORIGIN = "https://challenges.cloudflare.com";
// The Cloudflare proxy puts the Web Analytics script into the page; the code
// does not load it. A host, not a file, because the script URL has a version
// path after beacon.min.js. The beacon reports to /cdn-cgi/rum on the site
// itself, so connect-src needs nothing more.
const CLOUDFLARE_ANALYTICS_ORIGIN = "https://static.cloudflareinsights.com";

type Options = {
  // NEXT_PUBLIC_API_URL. The page streams answers from it.
  apiUrl: string | undefined;
  dev: boolean;
};

function apiOrigin(apiUrl: string | undefined): string | undefined {
  if (!apiUrl) return undefined;
  try {
    return new URL(apiUrl).origin;
  } catch {
    return undefined;
  }
}

// The policy has no nonce. A nonce needs each page to render on request, and
// the page is prerendered (cacheComponents), so scripts stay 'unsafe-inline' as
// in the "Without Nonces" form of the Next.js CSP guide. The protection here is
// in connect-src, frame-src, frame-ancestors, and object-src: the page shows
// model text as React text, never as HTML.
export function buildCsp({ apiUrl, dev }: Options): string {
  const api = apiOrigin(apiUrl);
  const directives = [
    "default-src 'self'",
    // React needs eval in development only, for its error stacks.
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""} ${TURNSTILE_ORIGIN} ${CLOUDFLARE_ANALYTICS_ORIGIN}`,
    // The charts render style attributes on the server.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    // next/font serves the Google fonts from the site.
    "font-src 'self'",
    `connect-src 'self'${api ? ` ${api}` : ""}`,
    `frame-src ${TURNSTILE_ORIGIN}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ];
  return directives.join("; ");
}

export function securityHeaders(options: Options): { key: string; value: string }[] {
  return [
    { key: "Content-Security-Policy", value: buildCsp(options) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    // For old browsers that do not read frame-ancestors.
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ];
}
