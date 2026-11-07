import { describe, expect, it } from "vitest";

import { chartSpecSchema } from "@/lib/analyst-schema";
import { LANDING_DATA, compareTile } from "@/lib/landing-data";

describe("landing data", () => {
  it("holds seven tiles that each pass the schema of an answer chart", () => {
    expect(LANDING_DATA.tiles.map((tile) => tile.chart.type)).toEqual([
      "shot_map",
      "heatmap",
      "pass_map",
      "pass_network",
      "xg_timeline",
      "points_pace",
      "compare_bars",
    ]);
    for (const tile of LANDING_DATA.tiles) {
      expect(chartSpecSchema.safeParse(tile.chart).success, tile.id).toBe(true);
      expect(tile.question).not.toBe("");
      expect(tile.label).not.toBe("");
    }
  });

  it("has a record of 38 league matches for each season", () => {
    for (const record of Object.values(LANDING_DATA.records)) {
      expect(record.won + record.drawn + record.lost).toBe(38);
    }
  });

  it("gives Henry first and Saka second in the compare bars", () => {
    const chart = compareTile();
    expect(chart.series.map((series) => series.player)).toEqual(["Thierry Henry", "Bukayo Saka"]);
    expect(chart.metrics.map((metric) => metric.name)).toEqual([
      "goals",
      "goals_per_90",
      "xg_per_90",
    ]);
  });

  it("stops when the data has no compare bars", () => {
    expect(() => compareTile({ ...LANDING_DATA, tiles: [] })).toThrow("compare bars");
  });

  it("has proof numbers that are not above their totals", () => {
    const { proof } = LANDING_DATA;
    expect(proof.correct).toBeLessThanOrEqual(proof.correctTotal);
    expect(proof.chartMatches).toBeLessThanOrEqual(proof.chartTotal);
    expect(proof.refusals).toBeLessThanOrEqual(proof.refusalTotal);
    expect(proof.runDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
