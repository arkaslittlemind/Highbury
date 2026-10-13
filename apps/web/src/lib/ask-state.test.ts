import { describe, expect, it } from "vitest";

import { answerDataSchema, chartSpecSchema, type Verification } from "@/lib/analyst-schema";
import {
  INITIAL_STATE,
  badgeState,
  chartsOfAnswer,
  formatCountdown,
  formatElapsed,
  reduce,
  retryOffer,
  secondsLeft,
  workingRowOf,
  type AskAction,
  type AskState,
} from "@/lib/ask-state";
import type { AskFailure } from "@/lib/ask-stream";
import { ANSWER_DATA, COMPARE_BARS, SHOT_MAP, STEP } from "@/lib/test-fixtures";

const DATA = answerDataSchema.parse(ANSWER_DATA);
const ID = DATA.conversation_id;
const SHOT_MAP_SPEC = chartSpecSchema.parse(SHOT_MAP);
const COMPARE_SPEC = chartSpecSchema.parse(COMPARE_BARS);

function run(...actions: AskAction[]): AskState {
  return actions.reduce(reduce, INITIAL_STATE);
}

function turnOf(state: AskState) {
  if (state.phase === "idle") throw new Error("The state has no turn.");
  return state.turn;
}

const ask = (question: string, asNew = false): AskAction => ({
  type: "ask",
  question,
  asNew,
  now: 1000,
});
const answer: AskAction = { type: "event", event: { type: "answer", data: DATA }, now: 4100 };
const fail = (failure: AskFailure): AskAction => ({
  type: "event",
  event: { type: "failure", failure },
  now: 2000,
});

describe("a turn", () => {
  it("starts a conversation with the first question", () => {
    const state = run(ask("Show the shots."));
    expect(state).toMatchObject({ phase: "asking", conversationId: null });
    expect(turnOf(state).followUp).toBe(false);
  });

  it("collects its steps and its charts in the order of their events", () => {
    const state = run(
      ask("Show the shots."),
      { type: "event", event: { type: "step", step: STEP }, now: 1500 },
      { type: "event", event: { type: "chart", chart: SHOT_MAP_SPEC }, now: 1600 },
      { type: "event", event: { type: "step", step: { ...STEP, number: 2 } }, now: 1700 },
    );
    expect(turnOf(state).steps.map((step) => step.number)).toEqual([1, 2]);
    expect(turnOf(state).charts).toEqual([SHOT_MAP_SPEC]);
  });

  it("keeps the conversation id of its answer", () => {
    const state = run(ask("Show the shots."), answer);
    expect(state).toMatchObject({ phase: "answered", conversationId: ID, endedAt: 4100 });
  });

  it("sends a follow-up in the conversation of the answer", () => {
    const state = run(ask("Show the shots."), answer, ask("Only the ones inside the box."));
    expect(state).toMatchObject({ phase: "asking", conversationId: ID });
    expect(turnOf(state).followUp).toBe(true);
    expect(turnOf(state).steps).toEqual([]);
  });

  it("starts a new conversation when the question is asked as new", () => {
    const state = run(ask("Show the shots."), answer, ask("Show the shots.", true));
    expect(state).toMatchObject({ phase: "asking", conversationId: null });
    expect(turnOf(state).followUp).toBe(false);
  });
});

describe("New question and Stop", () => {
  it("forgets the conversation and clears the bar on New question", () => {
    expect(run(ask("Show the shots."), answer, { type: "reset" })).toEqual(INITIAL_STATE);
  });

  it("forgets the conversation and puts the question back on Stop", () => {
    const state = run(
      ask("Show the shots."),
      answer,
      ask("Only the ones inside the box."),
      { type: "back_to_bar" },
    );
    expect(state).toEqual({
      phase: "idle",
      conversationId: null,
      draft: "Only the ones inside the box.",
    });
  });

  it("drops an event that comes after Stop", () => {
    const state = run(ask("Show the shots."), { type: "back_to_bar" }, answer);
    expect(state.phase).toBe("idle");
  });
});

describe("a failure", () => {
  const followUp = [ask("Show the shots."), answer, ask("Only the ones inside the box.")];

  it.each<AskFailure>([
    { kind: "agent", message: "The model call failed." },
    { kind: "conversation_ended" },
    { kind: "unexpected" },
  ])("forgets the conversation after $kind", (failure) => {
    expect(run(...followUp, fail(failure))).toMatchObject({
      phase: "failed",
      conversationId: null,
      endedAt: 2000,
    });
  });

  it.each<AskFailure>([
    { kind: "rate_limited", detail: "Too many questions.", retryAfterSeconds: 42 },
    { kind: "unreachable" },
    { kind: "http", message: null },
  ])("keeps the conversation after $kind", (failure) => {
    expect(run(...followUp, fail(failure))).toMatchObject({
      phase: "failed",
      conversationId: ID,
    });
  });

  it("sends a question again in its conversation after a rate limit", () => {
    const limited: AskFailure = { kind: "rate_limited", detail: "Wait.", retryAfterSeconds: 5 };
    const state = run(...followUp, fail(limited), ask("Only the ones inside the box."));
    expect(state).toMatchObject({ phase: "asking", conversationId: ID });
  });
});

describe("retryOffer", () => {
  const first = { question: "q", followUp: false, steps: [], charts: [], startedAt: 0 };
  const later = { ...first, followUp: true };

  it("offers a first question again after an error of the agent", () => {
    expect(retryOffer(first, { kind: "agent", message: "m" })).toBe("same");
    expect(retryOffer(first, { kind: "unexpected" })).toBe("same");
  });

  it("offers no retry for a follow-up whose conversation is gone", () => {
    expect(retryOffer(later, { kind: "agent", message: "m" })).toBe("none");
    expect(retryOffer(later, { kind: "unexpected" })).toBe("none");
  });

  it("offers a question as a new one after its conversation ended", () => {
    expect(retryOffer(later, { kind: "conversation_ended" })).toBe("as_new");
  });

  it("offers a follow-up again when its conversation is as it was", () => {
    expect(retryOffer(later, { kind: "unreachable" })).toBe("same");
    expect(retryOffer(later, { kind: "http", message: null })).toBe("same");
    expect(retryOffer(later, { kind: "rate_limited", detail: "d", retryAfterSeconds: 3 })).toBe(
      "same",
    );
  });
});

describe("badgeState", () => {
  const check = (change: Partial<Verification>): Verification => ({
    checked: 6,
    passed: 6,
    removed: [],
    unbacked_numbers: [],
    ...change,
  });

  it("shows no badge for an answer with nothing to check", () => {
    expect(badgeState(check({ checked: 0, passed: 0 }))).toBe("none");
  });

  it("is verified when each claim passed and each number has a claim", () => {
    expect(badgeState(check({}))).toBe("verified");
  });

  it("is partial when a claim was removed", () => {
    expect(badgeState(check({ passed: 5 }))).toBe("partial");
  });

  it("is partial when a number of the summary has no claim", () => {
    expect(badgeState(check({ unbacked_numbers: ["18"] }))).toBe("partial");
    expect(badgeState(check({ checked: 0, passed: 0, unbacked_numbers: ["18"] }))).toBe(
      "partial",
    );
  });
});

describe("chartsOfAnswer", () => {
  it("gives the charts in the order of the answer", () => {
    const charts = chartsOfAnswer(
      [{ id: COMPARE_SPEC.id }, { id: SHOT_MAP_SPEC.id }],
      [SHOT_MAP_SPEC, COMPARE_SPEC],
    );
    expect(charts.map(({ chart }) => chart?.type)).toEqual(["compare_bars", "shot_map"]);
  });

  it("leaves out a chart that the answer does not name", () => {
    expect(chartsOfAnswer([], [SHOT_MAP_SPEC])).toEqual([]);
  });

  it("gives null for an id with no valid chart", () => {
    expect(chartsOfAnswer([{ id: "chart_9" }], [SHOT_MAP_SPEC])).toEqual([
      { id: "chart_9", chart: null },
    ]);
  });

  it("uses the last chart when two have the same id", () => {
    const second = { ...SHOT_MAP_SPEC, title: "Built again" };
    const [{ chart }] = chartsOfAnswer([{ id: SHOT_MAP_SPEC.id }], [SHOT_MAP_SPEC, second]);
    expect(chart?.title).toBe("Built again");
  });
});

describe("workingRowOf", () => {
  it("finds the tool call that a claim cites", () => {
    const [claim] = DATA.answer.claims;
    expect(workingRowOf(DATA.working, claim.tool_call_id)).toBe(1);
  });

  it("gives null for an id that no tool call has", () => {
    const [{ claim }] = DATA.verification.removed;
    expect(workingRowOf(DATA.working, claim.tool_call_id)).toBeNull();
    expect(workingRowOf([], "q_1a2b3c4d")).toBeNull();
  });
});

describe("the texts of a time", () => {
  it("writes the elapsed time in seconds with one decimal", () => {
    expect(formatElapsed(3140)).toBe("3.1 s");
    expect(formatElapsed(0)).toBe("0.0 s");
    expect(formatElapsed(61250)).toBe("61.3 s");
    expect(formatElapsed(-5)).toBe("0.0 s");
  });

  it("counts the wait of a rate limit down to zero", () => {
    expect(secondsLeft(42, 1000, 1000)).toBe(42);
    expect(secondsLeft(42, 1000, 1500)).toBe(42);
    expect(secondsLeft(42, 1000, 42_000)).toBe(1);
    expect(secondsLeft(42, 1000, 43_000)).toBe(0);
    expect(secondsLeft(42, 1000, 90_000)).toBe(0);
  });

  it("writes the wait as minutes and seconds", () => {
    expect(formatCountdown(42)).toBe("0:42");
    expect(formatCountdown(5)).toBe("0:05");
    expect(formatCountdown(60)).toBe("1:00");
  });
});
