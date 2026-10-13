import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("joins class names and drops falsy values", () => {
    expect(cn("px-2", false, undefined, "text-sm")).toBe("px-2 text-sm");
  });
});
