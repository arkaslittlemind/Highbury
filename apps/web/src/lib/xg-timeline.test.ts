import { describe, expect, it } from "vitest";

import { XG_TIMELINE } from "@/lib/test-fixtures";
import {
  endMinute,
  markOrder,
  markPoints,
  minuteRows,
  shotLabel,
  summaryText,
  tooltipLines,
  tooltipHtml,
  xgAxis,
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

describe("minuteRows", () => {
  it("has one row per minute with each team's spec total after that minute", () => {
    const rows = minuteRows(CHART);
    expect(rows).toHaveLength(91);
    expect(rows[0]).toEqual({ minute: "0", t0: 0, t1: 0 });
    expect(rows[8]).toEqual({ minute: "8", t0: 0, t1: 0 });
    expect(rows[9]).toEqual({ minute: "9", t0: 0.13, t1: 0 });
    expect(rows[31]).toEqual({ minute: "31", t0: 0.55, t1: 0.07 });
    expect(rows[90]).toEqual({ minute: "90", t0: 1.33, t1: 0.07 });
  });

  it("takes the last total when two shots share a minute", () => {
    const twice = {
      ...ARSENAL,
      xg: 0.5,
      shots: [
        { minute: 20, xg: 0.2, total: 0.2, is_goal: false, player: "Robert Pires" },
        { minute: 20, xg: 0.3, total: 0.5, is_goal: true, player: "Thierry Henry" },
      ],
    };
    const rows = minuteRows(withTeams(twice, LIVERPOOL));
    expect(rows[19].t0).toBe(0);
    expect(rows[20].t0).toBe(0.5);
  });

  it("reaches a shot in stoppage time", () => {
    const late = {
      ...LIVERPOOL,
      xg: 0.37,
      shots: [
        ...LIVERPOOL.shots,
        { minute: 96, xg: 0.3, total: 0.37, is_goal: true, player: "Michael Owen" },
      ],
    };
    const rows = minuteRows(withTeams(ARSENAL, late));
    expect(rows).toHaveLength(97);
    expect(rows[95]).toEqual({ minute: "95", t0: 1.33, t1: 0.07 });
    expect(rows[96]).toEqual({ minute: "96", t0: 1.33, t1: 0.37 });
  });

  it("keeps a team with no shot at 0", () => {
    const rows = minuteRows(withTeams(ARSENAL, { ...LIVERPOOL, xg: 0, shots: [] }));
    expect(rows.every((row) => row.t1 === 0)).toBe(true);
  });
});

describe("markPoints", () => {
  it("gives the marks in keyboard order with team, minute, total, and goal", () => {
    expect(markPoints(CHART)).toEqual([
      { team: 0, minute: 9, total: 0.13, isGoal: false },
      { team: 0, minute: 31, total: 0.55, isGoal: true },
      { team: 1, minute: 31, total: 0.07, isGoal: false },
      { team: 0, minute: 49, total: 1.33, isGoal: true },
    ]);
  });
});

describe("tooltipHtml", () => {
  it("gives the tooltip lines, the first as the heading", () => {
    const [, henry] = markOrder(CHART);
    expect(tooltipHtml(henry)).toBe(
      '<div class="font-medium text-foreground">Goal · xG 0.42</div>' +
        "<div>Minute 31 · Thierry Henry</div>" +
        "<div>Arsenal total: 0.55 xG</div>",
    );
  });

  it("escapes a player name, because the tooltip renders HTML", () => {
    const shot = { minute: 5, xg: 0.1, total: 0.1, is_goal: false, player: "<b>A & B</b>" };
    const html = tooltipHtml({ team: 0, name: "Arsenal", shot });
    expect(html).toContain("Minute 5 · &lt;b&gt;A &amp; B&lt;/b&gt;");
    expect(html).not.toContain("<b>");
  });
});

describe("xgAxis", () => {
  it("goes to at least 1", () => {
    expect(xgAxis(withTeams({ ...ARSENAL, xg: 0.3 }, LIVERPOOL))).toEqual({ max: 1, interval: 0.25 });
  });

  it("rounds the highest total up to a half", () => {
    expect(xgAxis(CHART)).toEqual({ max: 1.5, interval: 0.5 });
    expect(xgAxis(withTeams({ ...ARSENAL, xg: 2.7 }, LIVERPOOL))).toEqual({ max: 3, interval: 0.5 });
  });

  it("rounds a high total up to a whole number", () => {
    expect(xgAxis(withTeams({ ...ARSENAL, xg: 4.2 }, LIVERPOOL))).toEqual({ max: 5, interval: 1 });
  });
});
