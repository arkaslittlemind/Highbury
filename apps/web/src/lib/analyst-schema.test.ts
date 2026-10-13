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
  SHOT,
  SHOT_MAP,
  STEP,
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

  it.each([SHOT_MAP, COMPARE_BARS, PASS_NETWORK])("accepts a valid $type chart", (chart) => {
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

  it("rejects a pass_network node with no passes", () => {
    const chart = { ...PASS_NETWORK, nodes: [{ ...PASS_NETWORK.nodes[0], passes: 0 }] };
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
