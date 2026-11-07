import { z } from "zod";

// The footer says "in the last 30 days", so the window and the text change together.
export const VISITS_DAYS = 30;
const DAY_MS = 24 * 60 * 60 * 1000;

export type VisitsWindow = { start: string; end: string };

export function visitsWindow(now: Date): VisitsWindow {
  return {
    start: new Date(now.getTime() - VISITS_DAYS * DAY_MS).toISOString(),
    end: now.toISOString(),
  };
}

// The Web Analytics dataset of the GraphQL Analytics API. sum.visits counts page
// views that came from another site or a direct link, as the Cloudflare dashboard does.
const QUERY = `query Visits($accountTag: string!, $siteTag: string!, $start: Time!, $end: Time!) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      rumPageloadEventsAdaptiveGroups(
        limit: 1
        filter: { siteTag: $siteTag, datetime_geq: $start, datetime_lt: $end }
      ) {
        sum { visits }
      }
    }
  }
}`;

export function visitsQuery({
  accountId,
  siteTag,
  window,
}: {
  accountId: string;
  siteTag: string;
  window: VisitsWindow;
}) {
  return {
    query: QUERY,
    variables: { accountTag: accountId, siteTag, start: window.start, end: window.end },
  };
}

const RESPONSE = z.object({
  data: z.object({
    viewer: z.object({
      accounts: z
        .array(
          z.object({
            rumPageloadEventsAdaptiveGroups: z.array(
              z.object({ sum: z.object({ visits: z.number().int().nonnegative() }) }),
            ),
          }),
        )
        .min(1),
    }),
  }),
  errors: z.array(z.unknown()).nullish(),
});

/**
 * The visit count of a GraphQL answer, or null when the answer cannot be trusted.
 * GraphQL answers 200 with an errors list, so the status code alone proves nothing.
 */
export function parseVisits(body: unknown): number | null {
  const parsed = RESPONSE.safeParse(body);
  if (!parsed.success || (parsed.data.errors?.length ?? 0) > 0) return null;
  const [group] = parsed.data.data.viewer.accounts[0].rumPageloadEventsAdaptiveGroups;
  // A window with no page view has no group.
  return group ? group.sum.visits : 0;
}

export function formatVisits(visits: number): string {
  return visits.toLocaleString("en-US");
}
