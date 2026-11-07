import { describe, expect, it } from "vitest";

import { formatVisits, parseVisits, visitsQuery, visitsWindow } from "@/lib/visits";

function body(groups: unknown[]) {
  return { data: { viewer: { accounts: [{ rumPageloadEventsAdaptiveGroups: groups }] } }, errors: null };
}

describe("visitsWindow", () => {
  it("is the 30 days that end at the given time", () => {
    const now = new Date("2026-11-07T12:00:00.000Z");
    expect(visitsWindow(now)).toEqual({
      start: "2026-10-08T12:00:00.000Z",
      end: "2026-11-07T12:00:00.000Z",
    });
  });
});

describe("visitsQuery", () => {
  it("puts the account, the site, and the window in the variables", () => {
    const request = visitsQuery({
      accountId: "acc",
      siteTag: "site",
      window: { start: "2026-10-08T12:00:00.000Z", end: "2026-11-07T12:00:00.000Z" },
    });
    expect(request.query).toContain("rumPageloadEventsAdaptiveGroups");
    expect(request.query).toContain("sum { visits }");
    expect(request.variables).toEqual({
      accountTag: "acc",
      siteTag: "site",
      start: "2026-10-08T12:00:00.000Z",
      end: "2026-11-07T12:00:00.000Z",
    });
  });
});

describe("parseVisits", () => {
  it("reads the visit sum", () => {
    expect(parseVisits(body([{ sum: { visits: 12480 } }]))).toBe(12480);
  });

  it("is null when the response has errors", () => {
    expect(
      parseVisits({ data: null, errors: [{ message: "not authorized for that account" }] }),
    ).toBeNull();
    expect(
      parseVisits({ ...body([{ sum: { visits: 5 } }]), errors: [{ message: "partial" }] }),
    ).toBeNull();
  });

  it("is zero when the site has no visits in the window", () => {
    // Cloudflare gives no group at all for a window with no events.
    expect(parseVisits(body([]))).toBe(0);
  });

  it("is null when the account is missing or the shape is wrong", () => {
    expect(parseVisits({ data: { viewer: { accounts: [] } }, errors: null })).toBeNull();
    expect(parseVisits(body([{ sum: { visits: "many" } }]))).toBeNull();
    expect(parseVisits(body([{ sum: { visits: -1 } }]))).toBeNull();
    expect(parseVisits("<html>")).toBeNull();
    expect(parseVisits(null)).toBeNull();
  });
});

describe("formatVisits", () => {
  it("groups the thousands with commas", () => {
    expect(formatVisits(12480)).toBe("12,480");
    expect(formatVisits(7)).toBe("7");
    expect(formatVisits(1234567)).toBe("1,234,567");
  });
});
