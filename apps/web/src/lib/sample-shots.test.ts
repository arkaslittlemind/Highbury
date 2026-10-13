import { describe, expect, it } from "vitest";

import { chartSpecSchema } from "@/lib/analyst-schema";
import { SAMPLE_SHOT_MAP } from "@/lib/sample-shots";
import { summaryText } from "@/lib/shot-map";

describe("the sample shot map", () => {
  it("passes the check that the page makes on a chart of the service", () => {
    expect(chartSpecSchema.safeParse(SAMPLE_SHOT_MAP).success).toBe(true);
  });

  it("holds the hat-trick of Henry against Liverpool", () => {
    expect(summaryText(SAMPLE_SHOT_MAP.shots)).toBe(
      "9 shots: 3 goals, 1 saved, 1 blocked, 4 off target. 7 from inside the penalty area.",
    );
  });
});
