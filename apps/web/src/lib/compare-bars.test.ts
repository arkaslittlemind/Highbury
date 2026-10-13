import { describe, expect, it } from "vitest";

import {
  barShare,
  hasModelCaveat,
  isCrossSeason,
  isModelMetric,
  metricLabel,
  summaryText,
  valueText,
  type CompareBarsSpec,
} from "@/lib/compare-bars";
import { COMPARE_BARS } from "@/lib/test-fixtures";

function chart(changes: Partial<CompareBarsSpec> = {}): CompareBarsSpec {
  return { ...COMPARE_BARS, type: "compare_bars", ...changes };
}

const SAME_SEASON = [
  { player: "Thierry Henry", season: "2003-04" },
  { player: "Robert Pires", season: "2003-04" },
];

describe("metricLabel", () => {
  it("starts a plain name with a capital", () => {
    expect(metricLabel("goals")).toBe("Goals");
    expect(metricLabel("assists")).toBe("Assists");
  });

  it("replaces each underscore with a space", () => {
    expect(metricLabel("shots_per_90")).toBe("Shots per 90");
  });

  it("writes the model words in their spelling, in any letter case", () => {
    expect(metricLabel("xg_per_90")).toBe("xG per 90");
    expect(metricLabel("XG")).toBe("xG");
    expect(metricLabel("npxg")).toBe("npxG");
    expect(metricLabel("goals_minus_xa")).toBe("Goals minus xA");
  });
});

describe("valueText", () => {
  it("shows a whole number with no decimals", () => {
    expect(valueText(30)).toBe("30");
    expect(valueText(0)).toBe("0");
  });

  it("shows two decimals at most and adds no zeros", () => {
    expect(valueText(0.61)).toBe("0.61");
    expect(valueText(0.6)).toBe("0.6");
    expect(valueText(2.456)).toBe("2.46");
  });

  it("shows a negative number", () => {
    expect(valueText(-1.5)).toBe("-1.5");
  });
});

describe("barShare", () => {
  it("gives the higher value the full width", () => {
    expect(barShare(30, 30)).toBe(100);
    expect(barShare(15, 30)).toBe(50);
  });

  it("gives no width when both values are 0", () => {
    expect(barShare(0, 0)).toBe(0);
  });

  it("gives no width to a negative value", () => {
    expect(barShare(-2, 4)).toBe(0);
    expect(barShare(-2, -1)).toBe(0);
  });
});

describe("isModelMetric", () => {
  it("is true for a name with a model word", () => {
    expect(isModelMetric("xg")).toBe(true);
    expect(isModelMetric("xg_per_90")).toBe(true);
    expect(isModelMetric("xA")).toBe(true);
    expect(isModelMetric("npxg_per_90")).toBe(true);
  });

  it("is false for other names, also with the letters xg inside a word", () => {
    expect(isModelMetric("goals")).toBe(false);
    expect(isModelMetric("boxgoals")).toBe(false);
  });
});

describe("isCrossSeason", () => {
  it("is true only for two different seasons", () => {
    expect(isCrossSeason(COMPARE_BARS.series)).toBe(true);
    expect(isCrossSeason(SAME_SEASON)).toBe(false);
  });
});

describe("hasModelCaveat", () => {
  it("needs two seasons and a model metric", () => {
    expect(hasModelCaveat(chart())).toBe(true);
    expect(hasModelCaveat(chart({ series: SAME_SEASON }))).toBe(false);
    expect(hasModelCaveat(chart({ metrics: [{ name: "goals", values: [30, 16] }] }))).toBe(false);
  });
});

describe("summaryText", () => {
  it("names the higher player of each metric and the model caveat", () => {
    expect(summaryText(chart())).toBe(
      "Goals: Thierry Henry (2003-04) is higher, 30 to 16." +
        " xG per 90: Thierry Henry (2003-04) is higher, 0.61 to 0.38." +
        " The two seasons use different xG models.",
    );
  });

  it("puts the higher value first when the second player is higher", () => {
    expect(summaryText(chart({ metrics: [{ name: "assists", values: [6, 11] }] }))).toBe(
      "Assists: Bukayo Saka (2025-26) is higher, 11 to 6.",
    );
  });

  it("says level for two equal values", () => {
    expect(summaryText(chart({ metrics: [{ name: "goals", values: [30, 30] }] }))).toBe(
      "Goals: level at 30.",
    );
  });

  it("has no sentence about the models for one season", () => {
    expect(
      summaryText(chart({ series: SAME_SEASON, metrics: [{ name: "xg", values: [20.5, 9.1] }] })),
    ).toBe("xG: Thierry Henry (2003-04) is higher, 20.5 to 9.1.");
  });
});
