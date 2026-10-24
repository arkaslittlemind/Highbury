import { describe, expect, it } from "vitest";

import {
  answerDataSchema,
  chartSpecSchema,
  errorDataSchema,
  stepSchema,
  suggestionsSchema,
} from "@/lib/analyst-schema";
import {
  ANSWER_DATA,
  COMPARE_BARS,
  PASS_NETWORK,
  POINTS_PACE,
  SHOT,
  SHOT_MAP,
  STEP,
  XG_TIMELINE,
} from "@/lib/test-fixtures";

describe("the payload of each event", () => {
  it("accepts a valid step, answer, error, and suggestions response", () => {
    expect(stepSchema.safeParse(STEP).success).toBe(true);
    expect(answerDataSchema.safeParse(ANSWER_DATA).success).toBe(true);
    expect(errorDataSchema.safeParse({ message: "The model call failed." }).success).toBe(true);
    expect(suggestionsSchema.safeParse({ suggestions: ["Show me the shots."] }).success).toBe(
      true,
    );
  });

  it.each([SHOT_MAP, COMPARE_BARS, PASS_NETWORK, XG_TIMELINE, POINTS_PACE])("accepts a valid $type chart", (chart) => {
    expect(chartSpecSchema.safeParse(chart).success).toBe(true);
  });

  it("keeps an answer when the service adds a field", () => {
    const withMore = {
      ...ANSWER_DATA,
      working: ANSWER_DATA.working.map((step) => ({ ...step, duration_ms: 12 })),
    };
    expect(answerDataSchema.safeParse(withMore).success).toBe(true);
  });

  it("rejects a working step with no call id key", () => {
    const working = ANSWER_DATA.working.map((step) => {
      const without: Record<string, unknown> = { ...step };
      delete without.call_id;
      return without;
    });
    expect(answerDataSchema.safeParse({ ...ANSWER_DATA, working }).success).toBe(false);
  });
});

describe("a payload that the service cannot send", () => {
  it.each([
    ["x off the pitch", { x: 999 }],
    ["y off the pitch", { y: -1 }],
    ["xG above 1", { xg: 1.2 }],
    ["a minute that is not whole", { minute: 12.5 }],
    ["an empty outcome", { outcome: "" }],
    ["a number as text", { xg: "0.52" }],
  ])("rejects a shot with %s", (_name, change) => {
    const chart = { ...SHOT_MAP, shots: [{ ...SHOT, ...change }] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it("rejects a compare_bars chart with three series", () => {
    const chart = { ...COMPARE_BARS, series: [...COMPARE_BARS.series, COMPARE_BARS.series[0]] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it("rejects a compare_bars chart with no metric", () => {
    expect(chartSpecSchema.safeParse({ ...COMPARE_BARS, metrics: [] }).success).toBe(false);
  });

  it("reads a pass_network with or without the minute its passes stop", () => {
    for (const until_minute of [71, null, undefined]) {
      expect(chartSpecSchema.safeParse({ ...PASS_NETWORK, until_minute }).success).toBe(true);
    }
  });

  it("rejects a pass_network minute that is not a match minute", () => {
    for (const until_minute of [131, -1, 71.5, "71"]) {
      expect(chartSpecSchema.safeParse({ ...PASS_NETWORK, until_minute }).success).toBe(false);
    }
  });

  it("rejects a pass_network node with no passes", () => {
    const chart = { ...PASS_NETWORK, nodes: [{ ...PASS_NETWORK.nodes[0], passes: 0 }] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it("rejects an xg_timeline with one team", () => {
    const chart = { ...XG_TIMELINE, teams: [XG_TIMELINE.teams[0]] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it.each([
    ["a minute after 130", { minute: 131 }],
    ["xG above 1", { xg: 1.2 }],
    ["a negative total", { total: -0.1 }],
    ["a goal as text", { is_goal: "true" }],
  ])("rejects an xg_timeline shot with %s", (_name, change) => {
    const [arsenal, opponent] = XG_TIMELINE.teams;
    const shots = [{ ...arsenal.shots[0], ...change }];
    const chart = { ...XG_TIMELINE, teams: [{ ...arsenal, shots }, opponent] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it.each([
    ["no line", []],
    ["five lines", Array(5).fill(POINTS_PACE.lines[0])],
  ])("rejects a points_pace with %s", (_name, lines) => {
    expect(chartSpecSchema.safeParse({ ...POINTS_PACE, lines }).success).toBe(false);
  });

  it.each([
    ["2 points", { points: 2 }],
    ["matchday 39", { matchday: 39 }],
    ["matchday 0", { matchday: 0 }],
    ["a negative total", { total: -1 }],
    ["goals as text", { goals_for: "2" }],
  ])("rejects a points_pace match with %s", (_name, change) => {
    const [first, second] = POINTS_PACE.lines;
    const matches = [{ ...first.matches[0], ...change }];
    const chart = { ...POINTS_PACE, lines: [{ ...first, matches }, second] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it("rejects a points_pace line with no match", () => {
    const chart = { ...POINTS_PACE, lines: [{ ...POINTS_PACE.lines[0], matches: [] }] };
    expect(chartSpecSchema.safeParse(chart).success).toBe(false);
  });

  it("rejects a chart of an unknown type", () => {
    expect(chartSpecSchema.safeParse({ ...SHOT_MAP, type: "heat_map" }).success).toBe(false);
  });

  it("rejects an answer with an unknown status", () => {
    const data = { ...ANSWER_DATA, answer: { ...ANSWER_DATA.answer, status: "guessed" } };
    expect(answerDataSchema.safeParse(data).success).toBe(false);
  });

  it("rejects an answer with no verification", () => {
    const data: Record<string, unknown> = { ...ANSWER_DATA };
    delete data.verification;
    expect(answerDataSchema.safeParse(data).success).toBe(false);
  });
});
