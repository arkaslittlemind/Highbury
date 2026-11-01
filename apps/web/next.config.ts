import type { NextConfig } from "next";

import { securityHeaders } from "./src/lib/security-headers";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  // The API URL is read at build time, as the bundle reads it, so a new API
  // origin needs a new build in both places.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders({
          apiUrl: process.env.NEXT_PUBLIC_API_URL,
          dev: process.env.NODE_ENV === "development",
        }),
      },
      // / answers HTML or Markdown by the Accept header, so a cache must keep
      // the two apart. Only the Markdown answer keeps this header: Next.js sets
      // its own Vary on the HTML page. Vercel runs the rewrite before its cache,
      // and Cloudflare does not cache HTML by default, so the two stay apart.
      { source: "/", headers: [{ key: "Vary", value: "Accept" }] },
    ];
  },
  async rewrites() {
    return {
      // beforeFiles, because / is a page: an afterFiles rewrite runs only when
      // no page matches. Browsers never ask for text/markdown, so they get HTML.
      beforeFiles: [
        {
          source: "/",
          has: [{ type: "header", key: "accept", value: ".*text/markdown.*" }],
          destination: "/index.md",
        },
      ],
    };
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
