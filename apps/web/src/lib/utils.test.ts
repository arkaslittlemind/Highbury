import { describe, expect, it } from "vitest";

import { cn, keepSeasonsWhole } from "@/lib/utils";

describe("cn", () => {
  it("joins class names and drops falsy values", () => {
    expect(cn("px-2", false, undefined, "text-sm")).toBe("px-2 text-sm");
  });
});

describe("keepSeasonsWhole", () => {
  it("joins the years of a season with a non-breaking hyphen", () => {
    expect(keepSeasonsWhole("the 2003-04 side and the 2025-26 side")).toBe(
      "the 2003‑04 side and the 2025‑26 side",
    );
  });

  it("leaves other hyphens alone", () => {
    expect(keepSeasonsWhole("a well-known 4-2 win in 2004")).toBe("a well-known 4-2 win in 2004");
  });
});
