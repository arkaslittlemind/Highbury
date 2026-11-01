import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

// AI search and the fetches that a person asks an assistant for: allowed, so
// assistants can find, read, and cite the site (/llms.txt is their guide).
const AI_SEARCH = [
  "OAI-SearchBot",
  "ChatGPT-User",
  "Claude-SearchBot",
  "Claude-User",
  "PerplexityBot",
  "Perplexity-User",
];

// AI training crawlers: blocked, by the user's choice (item 30b). This does not
// stop the search agents above, so assistants can still cite the site.
const AI_TRAINING = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: AI_SEARCH, allow: "/" },
      { userAgent: AI_TRAINING, disallow: "/" },
      // Search engines and every other crawler.
      { userAgent: "*", allow: "/" },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
