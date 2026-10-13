import { describe, expect, it } from "vitest";

import {
  drawOrder,
  isDrawn,
  nextIndex,
  outcomeKind,
  shotLabel,
  shotRadius,
  summaryText,
  tooltipLines,
  tooltipPlace,
  withoutKinds,
  type OutcomeKind,
  type Shot,
} from "@/lib/shot-map";
import { SHOT } from "@/lib/test-fixtures";

function shot(changes: Partial<Shot> = {}): Shot {
  return { ...SHOT, ...changes };
}

describe("shotRadius", () => {
  it("goes from 1 at an xG of 0 to 5 at an xG of 1", () => {
    expect(shotRadius(0)).toBe(1);
    expect(shotRadius(1)).toBe(5);
  });

  it("grows with xG, with the area in proportion", () => {
    expect(shotRadius(0.25)).toBe(3);
    expect(shotRadius(0.5)).toBeGreaterThan(shotRadius(0.25));
  });
});

describe("outcomeKind", () => {
  it("knows the five stored outcomes", () => {
    expect(outcomeKind("goal")).toBe("goal");
    expect(outcomeKind("saved")).toBe("saved");
    expect(outcomeKind("blocked")).toBe("blocked");
    expect(outcomeKind("off target")).toBe("off_target");
    expect(outcomeKind("post")).toBe("post");
  });

  it("gives other for a text that is not stored", () => {
    expect(outcomeKind("own goal")).toBe("other");
    expect(outcomeKind("Goal")).toBe("other");
    expect(outcomeKind("constructor")).toBe("other");
  });
});

describe("isDrawn", () => {
  it("is true for a shot in the attacking half and on the halfway line", () => {
    expect(isDrawn(shot({ x: 118 }))).toBe(true);
    expect(isDrawn(shot({ x: 60 }))).toBe(true);
  });

  it("is false for a shot from the own half", () => {
    expect(isDrawn(shot({ x: 59.9 }))).toBe(false);
  });
});

describe("drawOrder", () => {
  it("goes from the highest xG to the lowest", () => {
    const shots = [shot({ xg: 0.1 }), shot({ xg: 0.7 }), shot({ xg: 0.3 })];

    expect(drawOrder(shots).map((each) => each.xg)).toEqual([0.7, 0.3, 0.1]);
  });

  it("keeps the order of the data for an equal xG", () => {
    const shots = [shot({ xg: 0.2, minute: 5 }), shot({ xg: 0.2, minute: 80 })];

    expect(drawOrder(shots).map((each) => each.minute)).toEqual([5, 80]);
  });

  it("does not change the list that it gets", () => {
    const shots = [shot({ xg: 0.1 }), shot({ xg: 0.7 })];

    drawOrder(shots);

    expect(shots.map((each) => each.xg)).toEqual([0.1, 0.7]);
  });
});

describe("withoutKinds", () => {
  const shots = [
    shot({ outcome: "goal", minute: 1 }),
    shot({ outcome: "saved", minute: 2 }),
    shot({ outcome: "own goal", minute: 3 }),
    shot({ outcome: "goal", minute: 4 }),
  ];
  const minutes = (hidden: OutcomeKind[]) =>
    withoutKinds(shots, new Set(hidden)).map((each) => each.minute);

  it("gives all the shots when no kind is hidden", () => {
    expect(minutes([])).toEqual([1, 2, 3, 4]);
  });

  it("leaves out the shots of a hidden kind and keeps the order", () => {
    expect(minutes(["goal"])).toEqual([2, 3]);
  });

  it("hides an outcome that is not stored as other", () => {
    expect(minutes(["other"])).toEqual([1, 2, 4]);
  });

  it("gives no shots when each kind is hidden", () => {
    expect(minutes(["goal", "saved", "other"])).toEqual([]);
  });
});

describe("summaryText", () => {
  it("counts the shots, each outcome, and the shots in the penalty area", () => {
    const shots = [
      shot({ outcome: "saved" }),
      shot({ outcome: "goal" }),
      shot({ outcome: "off target", x: 90 }),
      shot({ outcome: "goal" }),
      shot({ outcome: "blocked" }),
      shot({ outcome: "goal" }),
      shot({ outcome: "saved" }),
    ];

    expect(summaryText(shots)).toBe(
      "7 shots: 3 goals, 2 saved, 1 blocked, 1 off target. 6 from inside the penalty area.",
    );
  });

  it("uses the singular for one shot and one goal", () => {
    expect(summaryText([shot()])).toBe("1 shot: 1 goal. 1 from inside the penalty area.");
  });

  it("names a shot off the post and a shot with an unknown outcome", () => {
    const shots = [shot({ outcome: "own goal" }), shot({ outcome: "post" })];

    expect(summaryText(shots)).toBe(
      "2 shots: 1 off the post, 1 other. 2 from inside the penalty area.",
    );
  });

  it("counts a shot on the line of the penalty area as inside", () => {
    const shots = [
      shot({ x: 102, y: 18 }),
      shot({ x: 101.9, y: 40 }),
      shot({ x: 110, y: 62.1 }),
    ];

    expect(summaryText(shots)).toBe("3 shots: 3 goals. 1 from inside the penalty area.");
  });

  it("counts a shot from the own half and says that it is not shown", () => {
    const shots = [shot(), shot({ x: 58, outcome: "off target" })];

    expect(summaryText(shots)).toBe(
      "2 shots: 1 goal, 1 off target. 1 from inside the penalty area. 1 shot from the own half is not shown.",
    );
  });

  it("uses the plural for two shots that are not shown", () => {
    const shots = [shot({ x: 10 }), shot({ x: 58 })];

    expect(summaryText(shots)).toBe(
      "2 shots: 2 goals. 0 from inside the penalty area. 2 shots from the own half are not shown.",
    );
  });
});

describe("shotLabel", () => {
  it("gives the outcome, the xG with two decimals, the minute and the opponent", () => {
    expect(shotLabel(shot({ xg: 0.5, player: null, match_date: null }))).toBe(
      "Goal, xG 0.50, minute 39, against Liverpool",
    );
  });

  it("adds the player and the match date when the chart has them", () => {
    expect(shotLabel(shot())).toBe(
      "Goal, xG 0.52, minute 39, against Liverpool, Thierry Henry, 2004-04-09",
    );
  });

  it("uses the text of an outcome that is not stored", () => {
    expect(shotLabel(shot({ outcome: "own goal", player: null, match_date: null }))).toBe(
      "own goal, xG 0.52, minute 39, against Liverpool",
    );
  });
});

describe("tooltipLines", () => {
  it("gives two lines for a shot with no player and no match date", () => {
    expect(tooltipLines(shot({ outcome: "off target", player: null, match_date: null }))).toEqual(
      ["Off target · xG 0.52", "Minute 39 · v Liverpool"],
    );
  });

  it("adds a line for the player and the match date", () => {
    expect(tooltipLines(shot())).toEqual([
      "Goal · xG 0.52",
      "Minute 39 · v Liverpool",
      "Thierry Henry · 2004-04-09",
    ]);
  });

  it("gives the match date alone when there is no player", () => {
    expect(tooltipLines(shot({ player: null }))[2]).toBe("2004-04-09");
  });
});

describe("tooltipPlace", () => {
  it("is below a mark in the top half of the drawing", () => {
    // xG 0.25 gives a radius of 3. The mark is at 40, 12 in a box of 84 x 66 from -2, -4.
    const place = tooltipPlace(shot({ x: 108, y: 40, xg: 0.25 }));

    expect(place.side).toBe("below");
    expect(place.left).toBeCloseTo(50);
    expect(place.top).toBeCloseTo((19 / 66) * 100);
  });

  it("is above a mark in the bottom half of the drawing", () => {
    const place = tooltipPlace(shot({ x: 70, y: 0, xg: 0.25 }));

    expect(place.side).toBe("above");
    expect(place.left).toBeCloseTo((2 / 84) * 100);
    expect(place.top).toBeCloseTo((51 / 66) * 100);
  });
});

describe("nextIndex", () => {
  it("moves to the next and the previous shot", () => {
    expect(nextIndex("ArrowRight", 1, 5)).toBe(2);
    expect(nextIndex("ArrowDown", 1, 5)).toBe(2);
    expect(nextIndex("ArrowLeft", 1, 5)).toBe(0);
    expect(nextIndex("ArrowUp", 1, 5)).toBe(0);
  });

  it("moves to the first and the last shot", () => {
    expect(nextIndex("Home", 3, 5)).toBe(0);
    expect(nextIndex("End", 1, 5)).toBe(4);
  });

  it("does not move past the first and the last shot", () => {
    expect(nextIndex("ArrowLeft", 0, 5)).toBe(0);
    expect(nextIndex("ArrowRight", 4, 5)).toBe(4);
  });

  it("gives null for a key that does not move", () => {
    expect(nextIndex("Enter", 1, 5)).toBeNull();
    expect(nextIndex("Tab", 1, 5)).toBeNull();
  });
});
