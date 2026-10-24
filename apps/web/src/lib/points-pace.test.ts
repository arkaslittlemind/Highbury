import { describe, expect, it } from "vitest";

import {
  VIEW,
  lineColours,
  linePath,
  markLabel,
  moveMark,
  scalesOf,
  summaryText,
  tooltipLines,
  tooltipPlace,
  type PaceLine,
  type PointsPaceSpec,
} from "@/lib/points-pace";
import { POINTS_PACE } from "@/lib/test-fixtures";

const CHART = POINTS_PACE as PointsPaceSpec;
const [INVINCIBLES, CURRENT] = CHART.lines;

function withLines(...lines: PaceLine[]): PointsPaceSpec {
  return { ...CHART, lines };
}

describe("scalesOf", () => {
  it("puts match 0 and match 38 inside the drawing", () => {
    const { x } = scalesOf(CHART);
    expect(x(0)).toBeGreaterThan(0);
    expect(x(38)).toBeLessThan(VIEW.width);
  });

  it("gives the points axis a top at or above the highest line", () => {
    expect(scalesOf(CHART).y.domain()[1]).toBeGreaterThanOrEqual(7);
  });

  it("puts more points above fewer", () => {
    const { y } = scalesOf(CHART);
    expect(y(7)).toBeLessThan(y(3));
  });
});

describe("linePath", () => {
  it("starts at 0 points before the first match and goes through each total", () => {
    const scales = scalesOf(CHART);
    const corners = [
      [0, 0],
      [1, 3],
      [2, 4],
      [3, 7],
    ].map(([matchday, total]) => `${scales.x(matchday)} ${scales.y(total)}`);
    expect(linePath(INVINCIBLES, scales)).toBe(`M${corners.join("L")}`);
  });
});

describe("lineColours", () => {
  it("gives each Arsenal line the colour of its season", () => {
    expect(lineColours(CHART)).toEqual([0, 1]);
  });

  it("gives the other lines the next colours", () => {
    const city = { ...CURRENT, team: "Manchester City" };
    const chelsea = { ...INVINCIBLES, team: "Chelsea" };
    expect(lineColours(withLines(CURRENT, city, chelsea))).toEqual([1, 2, 3]);
  });
});

describe("moveMark", () => {
  it("goes along a line and stops at its ends", () => {
    expect(moveMark("ArrowRight", { line: 0, match: 0 }, CHART)).toEqual({ line: 0, match: 1 });
    expect(moveMark("ArrowRight", { line: 0, match: 2 }, CHART)).toEqual({ line: 0, match: 2 });
    expect(moveMark("ArrowLeft", { line: 0, match: 0 }, CHART)).toEqual({ line: 0, match: 0 });
    expect(moveMark("End", { line: 0, match: 0 }, CHART)).toEqual({ line: 0, match: 2 });
    expect(moveMark("Home", { line: 0, match: 2 }, CHART)).toEqual({ line: 0, match: 0 });
  });

  it("goes to the same matchday of the next line, or its last match", () => {
    expect(moveMark("ArrowDown", { line: 0, match: 1 }, CHART)).toEqual({ line: 1, match: 1 });
    expect(moveMark("ArrowDown", { line: 0, match: 2 }, CHART)).toEqual({ line: 1, match: 1 });
    expect(moveMark("ArrowUp", { line: 1, match: 0 }, CHART)).toEqual({ line: 0, match: 0 });
  });

  it("stays on the first and the last line", () => {
    expect(moveMark("ArrowUp", { line: 0, match: 1 }, CHART)).toEqual({ line: 0, match: 1 });
    expect(moveMark("ArrowDown", { line: 1, match: 1 }, CHART)).toEqual({ line: 1, match: 1 });
  });

  it("ignores a key that does not move", () => {
    expect(moveMark("Enter", { line: 0, match: 0 }, CHART)).toBeNull();
  });
});

describe("the text of a mark", () => {
  const draw = INVINCIBLES.matches[1];

  it("names the line, the match, the result, and the total", () => {
    expect(markLabel(INVINCIBLES, draw)).toBe(
      "Arsenal 2003-04, match 2, 2003-08-24, D 1-1 v Portsmouth, 4 points in total",
    );
    expect(tooltipLines(INVINCIBLES, draw)).toEqual([
      "Arsenal 2003-04 · Match 2",
      "D 1-1 v Portsmouth · 2003-08-24",
      "Total: 4 points",
    ]);
  });
});

describe("tooltipPlace", () => {
  it("is at the match, on the side with more room", () => {
    const scales = scalesOf(CHART);
    const low = tooltipPlace(CURRENT.matches[0], scales);
    expect(low.left).toBeCloseTo((scales.x(1) / VIEW.width) * 100);
    expect(low.side).toBe("above");
    expect(tooltipPlace(INVINCIBLES.matches[2], scales).side).toBe("below");
  });
});

describe("summaryText", () => {
  it("gives the points, matches, and results of each line", () => {
    expect(summaryText(CHART)).toBe(
      "Arsenal 2003-04: 7 points from 3 matches (2 won, 1 drawn, 0 lost)." +
        " Arsenal 2025-26: 3 points from 2 matches (1 won, 0 drawn, 1 lost).",
    );
  });

  it("reads correctly for one match", () => {
    const one = { ...CURRENT, points: 3, matches: [CURRENT.matches[0]] };
    expect(summaryText(withLines(one))).toBe(
      "Arsenal 2025-26: 3 points from 1 match (1 won, 0 drawn, 0 lost).",
    );
  });
});
