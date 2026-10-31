import { describe, expect, it } from "vitest";

import {
  busiestZone,
  keyOpacities,
  MAX_OPACITY,
  MIN_OPACITY,
  shareText,
  summaryText,
  tooltipLines,
  zoneLabel,
  zoneOpacity,
  zonePlace,
  zoneRect,
  type HeatmapSpec,
} from "@/lib/heatmap";
import { HEATMAP } from "@/lib/test-fixtures";

const chart = HEATMAP as HeatmapSpec;

describe("zoneRect", () => {
  it("puts the zone at the own goal line at the bottom left of the drawing", () => {
    expect(zoneRect({ zone_x: 0, zone_y: 0, touches: 1 })).toEqual({
      x: 0,
      y: 110,
      width: 10,
      height: 10,
    });
  });

  it("puts the far right zone of the attack at the top right", () => {
    expect(zoneRect({ zone_x: 11, zone_y: 7, touches: 1 })).toEqual({
      x: 70,
      y: 0,
      width: 10,
      height: 10,
    });
  });
});

describe("zoneOpacity", () => {
  it("goes from the faintest shade to the strongest at the busiest zone", () => {
    expect(zoneOpacity(0, 60)).toBe(MIN_OPACITY);
    expect(zoneOpacity(60, 60)).toBe(MAX_OPACITY);
    expect(zoneOpacity(30, 60)).toBeCloseTo((MIN_OPACITY + MAX_OPACITY) / 2);
  });
});

describe("keyOpacities", () => {
  it("starts at the shade of the fewest zone and ends at the busiest", () => {
    const shades = keyOpacities(20, 60, 5);
    expect(shades).toHaveLength(5);
    expect(shades[0]).toBe(zoneOpacity(20, 60));
    expect(shades[4]).toBe(MAX_OPACITY);
    for (let step = 1; step < shades.length; step++) {
      expect(shades[step]).toBeGreaterThan(shades[step - 1]);
    }
  });

  it("gives every step the strongest shade when every zone has the same count", () => {
    expect(keyOpacities(7, 7, 5)).toEqual(Array(5).fill(MAX_OPACITY));
  });
});

describe("shareText", () => {
  it("rounds to a whole % and does not call a small share none", () => {
    expect(shareText(60, 100)).toBe("60%");
    expect(shareText(1, 3)).toBe("33%");
    expect(shareText(1, 400)).toBe("<1%");
    expect(shareText(0, 400)).toBe("0%");
  });
});

describe("zonePlace", () => {
  it.each([
    [{ zone_x: 0, zone_y: 0 }, "Defensive third, left"],
    [{ zone_x: 4, zone_y: 3 }, "Middle third, centre"],
    [{ zone_x: 7, zone_y: 4 }, "Middle third, centre"],
    [{ zone_x: 8, zone_y: 5 }, "Final third, right"],
    [{ zone_x: 11, zone_y: 2 }, "Final third, left"],
  ])("names the zone %o", (zone, place) => {
    expect(zonePlace({ ...zone, touches: 1 })).toBe(place);
  });
});

describe("busiestZone", () => {
  it("takes the most touches, and the first zone on a tie", () => {
    expect(busiestZone(chart.zones)).toBe(chart.zones[0]);
    const tie = [
      { zone_x: 1, zone_y: 1, touches: 5 },
      { zone_x: 2, zone_y: 2, touches: 5 },
    ];
    expect(busiestZone(tie)).toBe(tie[0]);
  });
});

describe("summaryText", () => {
  it("gives the total, the final third, and the busiest zone", () => {
    expect(summaryText(chart)).toBe(
      "100 touches. 60% in the final third. Busiest zone: 60 touches (final third, left).",
    );
  });

  it("writes large counts with a comma and one touch as one", () => {
    const one = {
      ...chart,
      total: 1,
      zones: [{ zone_x: 2, zone_y: 3, touches: 1 }],
    };
    expect(summaryText(one)).toBe(
      "1 touch. 0% in the final third. Busiest zone: 1 touch (defensive third, centre).",
    );
    const many = {
      ...chart,
      total: 2218,
      zones: [{ zone_x: 9, zone_y: 4, touches: 2218 }],
    };
    expect(summaryText(many)).toMatch(/^2,218 touches\. 100% in the final third\./);
  });

  it("says under 1% for a small final third", () => {
    const zones = [
      { zone_x: 2, zone_y: 3, touches: 399 },
      { zone_x: 9, zone_y: 3, touches: 1 },
    ];
    expect(summaryText({ ...chart, total: 400, zones })).toMatch(/^400 touches\. Under 1% in/);
  });
});

describe("zoneLabel and tooltipLines", () => {
  it("give the touches, the share, and the place", () => {
    const zone = chart.zones[1];
    expect(zoneLabel(zone, chart.total)).toBe("30 touches, 30% of all, middle third, centre");
    expect(tooltipLines(zone, chart.total)).toEqual([
      "30 touches · 30% of all",
      "Middle third, centre",
    ]);
  });
});
