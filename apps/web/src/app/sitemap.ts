import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

// The site has one page. Answers are not pages, so they are not listed.
export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: `${SITE_URL}/` }];
}
