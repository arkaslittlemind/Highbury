import { describe, expect, it } from "vitest";

import { XG_TIMELINE } from "@/lib/test-fixtures";
import {
  VIEW,
  endMinute,
  linePath,
  markOrder,
  scalesOf,
  shotLabel,
  stepPoints,
  summaryText,
  tooltipLines,
  tooltipPlace,
  type TimelineTeam,
  type XgTimelineSpec,
} from "@/lib/xg-timeline";

const CHART = XG_TIMELINE as XgTimelineSpec;
const [ARSENAL, LIVERPOOL] = CHART.teams;

function withTeams(first: TimelineTeam, second: TimelineTeam): XgTimelineSpec {
  return { ...CHART, teams: [first, second] };
}

describe("endMinute", () => {
  it("is 90 when every shot is earlier", () => {
    expect(endMinute(CHART)).toBe(90);
  });

  it("is the minute of a shot in stoppage time", () => {
    const late = { ...LIVERPOOL, shots: [{ ...LIVERPOOL.shots[0], minute: 94 }] };
    expect(endMinute(withTeams(ARSENAL, late))).toBe(94);
  });
});

describe("stepPoints", () => {
  it("is flat until a shot and goes up to its total", () => {
    expect(stepPoints(ARSENAL, 90)).toEqual([
      { minute: 0, xg: 0 },
      { minute: 9, xg: 0 },
      { minute: 9, xg: 0.13 },
      { minute: 31, xg: 0.13 },
      { minute: 31, xg: 0.55 },
      { minute: 49, xg: 0.55 },
      { minute: 49, xg: 1.33 },
      { minute: 90, xg: 1.33 },
    ]);
  });

  it("is one flat line at 0 for a team with no shot", () => {
    expect(stepPoints({ ...LIVERPOOL, xg: 0, shots: [] }, 93)).toEqual([
      { minute: 0, xg: 0 },
      { minute: 93, xg: 0 },
    ]);
  });
});

describe("scalesOf", () => {
  it("puts minute 0 and the last minute inside the drawing", () => {
    const { x } = scalesOf(CHART);
    expect(x(0)).toBeGreaterThan(0);
    expect(x(90)).toBeLessThan(VIEW.width);
  });

  it("gives the xG axis a top of at least 1", () => {
    const { y } = scalesOf(withTeams({ ...ARSENAL, xg: 0.3, shots: [] }, LIVERPOOL));
    expect(y.domain()).toEqual([0, 1]);
  });

  it("puts a higher total above a lower one", () => {
    const { y } = scalesOf(CHART);
    expect(y.domain()[1]).toBeGreaterThanOrEqual(1.33);
    expect(y(1.33)).toBeLessThan(y(0.07));
  });
});

describe("linePath", () => {
  it("moves to the first corner and draws a line to each other one", () => {
    const scales = scalesOf(CHART);
    const path = linePath(stepPoints({ ...LIVERPOOL, xg: 0, shots: [] }, 90), scales);
    expect(path).toBe(`M${scales.x(0)} ${scales.y(0)}L${scales.x(90)} ${scales.y(0)}`);
  });
});

describe("markOrder", () => {
  it("orders the shots of both teams by minute, Arsenal first on a tie", () => {
    expect(markOrder(CHART).map(({ name, shot }) => `${name} ${shot.minute}`)).toEqual([
      "Arsenal 9",
      "Arsenal 31",
      "Liverpool 31",
      "Arsenal 49",
    ]);
  });
});

describe("the text of a mark", () => {
  const [, henry, , unnamed] = markOrder(CHART);

  it("names the goal, the player, the team, the minute, and both xG values", () => {
    expect(shotLabel(henry)).toBe(
      "Goal, Thierry Henry, Arsenal, minute 31, xG 0.42, Arsenal total 0.55 xG",
    );
    expect(tooltipLines(henry)).toEqual([
      "Goal · xG 0.42",
      "Minute 31 · Thierry Henry",
      "Arsenal total: 0.55 xG",
    ]);
  });

  it("uses the team when the shot has no player", () => {
    expect(shotLabel(unnamed)).toBe("Goal, Arsenal, minute 49, xG 0.78, Arsenal total 1.33 xG");
    expect(tooltipLines(unnamed)[1]).toBe("Minute 49 · Arsenal");
  });
});

describe("tooltipPlace", () => {
  it("is at the minute of the shot, on the side with more room", () => {
    const scales = scalesOf(CHART);
    const [first, , , last] = markOrder(CHART);

    const low = tooltipPlace(first, scales);
    expect(low.side).toBe("above");
    expect(low.left).toBeCloseTo((scales.x(9) / VIEW.width) * 100);

    // The top of the axis is 1.5, so a total of 1.33 is in the upper half.
    expect(tooltipPlace(last, scales).side).toBe("below");
  });
});

describe("summaryText", () => {
  it("gives the total, shots, and goals of each team and the own-goal note", () => {
    expect(summaryText(CHART)).toBe(
      "Arsenal: 1.33 xG from 3 shots, 2 goals (Thierry Henry 31', 49')." +
        " Liverpool: 0.07 xG from 1 shot, no goal." +
        " Own goals are not shots, so they have no mark.",
    );
  });

  it("reads correctly for a team with no shot", () => {
    const none = { ...LIVERPOOL, xg: 0, shots: [] };
    expect(summaryText(withTeams(ARSENAL, none))).toContain(
      "Liverpool: 0.00 xG from 0 shots, no goal.",
    );
  });
});
