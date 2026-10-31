import { describe, expect, it } from "vitest";

import {
  passKind,
  passLabel,
  passLength,
  summaryText,
  tooltipLines,
  tooltipPlace,
  withoutKinds,
  type Pass,
} from "@/lib/pass-map";
import { PASS } from "@/lib/test-fixtures";

function pass(changes: Partial<Pass> = {}): Pass {
  return { ...PASS, ...changes };
}

describe("passKind", () => {
  it("calls a pass with no outcome completed and any other pass incomplete", () => {
    expect(passKind(pass())).toBe("completed");
    expect(passKind(pass({ outcome: "out" }))).toBe("incomplete");
    expect(passKind(pass({ outcome: "incomplete" }))).toBe("incomplete");
  });
});

describe("passLength", () => {
  it("is the straight distance from the start to the end, in yards", () => {
    expect(passLength(pass({ x: 10, y: 10, end_x: 40, end_y: 50 }))).toBe(50);
    expect(passLength(pass({ x: 10, y: 10, end_x: 10, end_y: 10 }))).toBe(0);
  });
});

describe("withoutKinds", () => {
  it("leaves out the passes of the hidden kinds and keeps the order", () => {
    const passes = [pass({ minute: 1 }), pass({ minute: 2, outcome: "out" }), pass({ minute: 3 })];

    expect(withoutKinds(passes, new Set()).map((p) => p.minute)).toEqual([1, 2, 3]);
    expect(withoutKinds(passes, new Set(["incomplete"])).map((p) => p.minute)).toEqual([1, 3]);
    expect(withoutKinds(passes, new Set(["completed", "incomplete"]))).toEqual([]);
  });
});

describe("summaryText", () => {
  it("gives the count, the completed share, and the longest pass", () => {
    const passes = [
      pass({ x: 10, y: 10, end_x: 40, end_y: 50 }),
      pass({ x: 0, y: 0, end_x: 68, end_y: 0, outcome: "out" }),
      pass({ x: 0, y: 0, end_x: 36, end_y: 0 }),
    ];

    expect(summaryText(passes)).toBe("3 passes, 2 completed (67%). Longest: 68 yards.");
  });

  it("says pass for one pass", () => {
    expect(summaryText([pass({ x: 0, y: 0, end_x: 35.4, end_y: 0 })])).toBe(
      "1 pass, 1 completed (100%). Longest: 35 yards.",
    );
  });
});

describe("the words of a pass", () => {
  it("name the recipient of a completed pass", () => {
    expect(tooltipLines(pass())).toEqual([
      "To Thierry Henry · 54 yards",
      "Minute 12 · v Everton",
      "2003-08-16",
    ]);
    expect(passLabel(pass())).toBe(
      "To Thierry Henry, 54 yards, minute 12, against Everton, 2003-08-16",
    );
  });

  it("give the reason of a failed pass in place of a recipient", () => {
    const failed = pass({ outcome: "out", recipient: null, match_date: null });

    expect(tooltipLines(failed)).toEqual(["Incomplete: out · 54 yards", "Minute 12 · v Everton"]);
    expect(passLabel(failed)).toBe("Incomplete: out, 54 yards, minute 12, against Everton");
  });

  it("do not repeat the kind when the reason is incomplete", () => {
    const failed = pass({ outcome: "incomplete", recipient: null });

    expect(tooltipLines(failed)[0]).toBe("Incomplete · 54 yards");
    expect(passLabel(failed)).toBe("Incomplete, 54 yards, minute 12, against Everton, 2003-08-16");
  });

  it("say completed for a completed pass with no recipient", () => {
    expect(tooltipLines(pass({ recipient: undefined }))[0]).toBe("Completed · 54 yards");
  });
});

describe("tooltipPlace", () => {
  it("puts the tooltip at the end of the arrow, on the side with more room", () => {
    // The end at x = 90 is in the top half of the drawing, so the tooltip is below it.
    expect(tooltipPlace(pass()).side).toBe("below");
    expect(tooltipPlace(pass({ end_x: 20 })).side).toBe("above");
  });
});
