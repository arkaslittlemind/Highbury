import { describe, expect, it } from "vitest";

import { isInPenaltyArea, toPitchPoint, tooltipPlaceAt, viewBoxOf } from "@/lib/pitch";

describe("toPitchPoint", () => {
  it("puts the centre of the goal line of the attack at the top", () => {
    expect(toPitchPoint(120, 40)).toEqual({ x: 40, y: 0 });
  });

  it("puts the penalty spot 12 units below the goal line", () => {
    const spot = toPitchPoint(108, 40);

    expect(spot.x).toBe(40);
    expect(spot.y).toBeCloseTo(12);
  });

  it("puts the left touchline of the attacker at the left of the screen", () => {
    expect(toPitchPoint(100, 0).x).toBe(0);
    expect(toPitchPoint(100, 80).x).toBe(80);
  });

  it("puts the halfway line and the own goal line below the attack", () => {
    expect(toPitchPoint(60, 40).y).toBe(60);
    expect(toPitchPoint(0, 40).y).toBe(120);
  });
});

describe("viewBoxOf", () => {
  it("shows the attacking half", () => {
    expect(viewBoxOf("attacking-half")).toEqual({ minX: -2, minY: -4, width: 84, height: 66 });
  });

  it("shows the full pitch", () => {
    expect(viewBoxOf("full")).toEqual({ minX: -2, minY: -4, width: 84, height: 126 });
  });
});

describe("tooltipPlaceAt", () => {
  it("is below a mark in the top half of the full pitch", () => {
    // The box of the full view is 84 x 126 from -2, -4.
    const place = tooltipPlaceAt({ x: 40, y: 20 }, 3, "full");

    expect(place).toEqual({ left: 50, top: (27 / 126) * 100, side: "below" });
  });

  it("is above a mark in the bottom half of the full pitch", () => {
    const place = tooltipPlaceAt({ x: 80, y: 100 }, 3, "full");

    expect(place.side).toBe("above");
    expect(place.left).toBeCloseTo((82 / 84) * 100);
    expect(place.top).toBeCloseTo((101 / 126) * 100);
  });
});

describe("isInPenaltyArea", () => {
  it("is true inside the area and on its lines", () => {
    expect(isInPenaltyArea(110, 40)).toBe(true);
    expect(isInPenaltyArea(102, 18)).toBe(true);
    expect(isInPenaltyArea(120, 62)).toBe(true);
  });

  it("is false outside the area", () => {
    expect(isInPenaltyArea(101.9, 40)).toBe(false);
    expect(isInPenaltyArea(110, 17.9)).toBe(false);
    expect(isInPenaltyArea(110, 62.1)).toBe(false);
    expect(isInPenaltyArea(10, 40)).toBe(false);
  });
});
