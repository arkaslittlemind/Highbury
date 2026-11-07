import { cacheLife } from "next/cache";

import { formatVisits, parseVisits, VISITS_DAYS, visitsQuery, visitsWindow } from "@/lib/visits";

const GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql";
const TIMEOUT_MS = 5000;

/**
 * The visits of the last 30 days from Cloudflare Web Analytics. It runs on the
 * server only, so the token never reaches the browser, and the browser never
 * calls Cloudflare. Every failure is null: a missing count must not break the
 * page or the build. A null is cached too, so a failed fetch stays hidden until
 * the next revalidation, one hour later.
 */
async function getVisits(): Promise<number | null> {
  "use cache";
  cacheLife("hours");

  // Server-only names, with no NEXT_PUBLIC_ prefix, so Next.js never puts them into the bundle.
  const token = process.env.CLOUDFLARE_ANALYTICS_TOKEN;
  const accountId = process.env.CLOUDFLARE_ACCOUNT_ID;
  const siteTag = process.env.CLOUDFLARE_SITE_TAG;
  if (!token || !accountId || !siteTag) return null;

  try {
    const response = await fetch(GRAPHQL_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(visitsQuery({ accountId, siteTag, window: visitsWindow(new Date()) })),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    return parseVisits(await response.json());
  } catch {
    // The reason is not logged: a log line could carry the request, and the
    // footer has no use for it.
    return null;
  }
}

export async function VisitCount() {
  const visits = await getVisits();
  if (visits === null) return null;
  return (
    <p
      className="inline-flex items-center gap-2 text-sm text-muted-foreground"
      title="Visits counted by Cloudflare Web Analytics, refreshed hourly"
    >
      <svg
        aria-hidden="true"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="flex-none text-verified"
      >
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      <span>
        <b className="font-semibold text-foreground tabular-nums">{formatVisits(visits)}</b> visits
        in the last {VISITS_DAYS} days
      </span>
    </p>
  );
}
