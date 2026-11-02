import { afterEach, describe, expect, it, vi } from "vitest";

import { askStream, failureFromResponse, readEvents, type AskEvent } from "@/lib/ask-stream";
import { ANSWER_DATA, SHOT, SHOT_MAP, STEP, sse } from "@/lib/test-fixtures";

async function eventsOf(...chunks: string[]): Promise<AskEvent[]> {
  async function* stream() {
    yield* chunks;
  }
  const events: AskEvent[] = [];
  for await (const event of readEvents(stream())) events.push(event);
  return events;
}

const UNEXPECTED = { type: "failure", failure: { kind: "unexpected" } };

describe("readEvents", () => {
  it("gives the step, the chart, and the answer of a turn", async () => {
    const events = await eventsOf(
      sse("step", STEP) + sse("chart", SHOT_MAP) + sse("answer", ANSWER_DATA),
    );
    expect(events.map((event) => event.type)).toEqual(["step", "chart", "answer"]);
    expect(events[0]).toEqual({ type: "step", step: STEP });
  });

  it("joins an event that comes in two reads", async () => {
    const text = sse("step", STEP);
    const events = await eventsOf(text.slice(0, 20), text.slice(20) + sse("answer", ANSWER_DATA));
    expect(events.map((event) => event.type)).toEqual(["step", "answer"]);
  });

  it("joins an event whose end mark comes in two reads", async () => {
    const text = sse("step", STEP);
    const events = await eventsOf(text.slice(0, -1), "\n" + sse("answer", ANSWER_DATA));
    expect(events.map((event) => event.type)).toEqual(["step", "answer"]);
  });

  it("gives an unexpected failure for a stream that is cut", async () => {
    const answer = sse("answer", ANSWER_DATA);
    const events = await eventsOf(sse("step", STEP), answer.slice(0, 40));
    expect(events).toEqual([{ type: "step", step: STEP }, UNEXPECTED]);
  });

  it("gives an unexpected failure for a stream with no event", async () => {
    expect(await eventsOf()).toEqual([UNEXPECTED]);
  });

  it.each([
    ["no event line", 'data: {"number": 1}\n\n'],
    ["data that is not JSON", "event: step\ndata: {not json\n\n"],
    ["a step of a wrong form", sse("step", { number: "one" })],
    ["an answer of a wrong form", sse("answer", { ...ANSWER_DATA, answer: null })],
    ["an error of a wrong form", sse("error", { detail: "no message" })],
  ])("gives an unexpected failure for %s, and reads no more", async (_name, bad) => {
    expect(await eventsOf(bad + sse("answer", ANSWER_DATA))).toEqual([UNEXPECTED]);
  });

  it("gives the message of an error event, and reads no more", async () => {
    const events = await eventsOf(
      sse("error", { message: "The model call failed." }) + sse("step", STEP),
    );
    expect(events).toEqual([
      { type: "failure", failure: { kind: "agent", message: "The model call failed." } },
    ]);
  });

  it("drops a chart that fails its schema, and keeps the turn", async () => {
    const badChart = { ...SHOT_MAP, shots: [{ ...SHOT, x: 999 }] };
    const events = await eventsOf(sse("chart", badChart) + sse("answer", ANSWER_DATA));
    expect(events.map((event) => event.type)).toEqual(["answer"]);
  });

  it("drops an event that it does not know", async () => {
    const events = await eventsOf(sse("ping", {}) + sse("answer", ANSWER_DATA));
    expect(events.map((event) => event.type)).toEqual(["answer"]);
  });
});

describe("failureFromResponse", () => {
  const detail = "Too many questions. Try again in 42 seconds.";

  it("gives the wait of a 429 from its header", () => {
    expect(failureFromResponse(429, "42", { detail })).toEqual({
      kind: "rate_limited",
      detail,
      retryAfterSeconds: 42,
    });
  });

  it.each([null, "soon", "0", "-5", "1.5"])(
    "gives no wait for a 429 with the header %s",
    (header) => {
      expect(failureFromResponse(429, header, { detail })).toEqual({
        kind: "rate_limited",
        detail,
        retryAfterSeconds: null,
      });
    },
  );

  it.each([
    [429, "address", "You have asked 10 questions today. Come back tomorrow."],
    [503, "site", "Highbury has answered all the questions it can today. Come back tomorrow."],
  ] as const)("names a daily limit from its header: %i %s", (status, scope, text) => {
    expect(failureFromResponse(status, null, { detail: text }, scope)).toEqual({
      kind: "daily_limited",
      scope,
      detail: text,
    });
  });

  it("gives a daily limit a text when the body has none", () => {
    expect(failureFromResponse(429, null, null, "address")).toEqual({
      kind: "daily_limited",
      scope: "address",
      detail: "Come back tomorrow.",
    });
  });

  it("keeps the wait of a 429 that names no daily limit", () => {
    expect(failureFromResponse(429, "42", { detail }, null)).toEqual({
      kind: "rate_limited",
      detail,
      retryAfterSeconds: 42,
    });
  });

  it.each([null, "", "minute", "Address"])(
    "treats a daily header of %s as no daily limit",
    (header) => {
      const busy = { detail: "Highbury is busy. Try again in a minute." };
      expect(failureFromResponse(503, null, busy, header)).toEqual({
        kind: "http",
        message: busy.detail,
      });
      expect(failureFromResponse(429, null, { detail }, header)).toEqual({
        kind: "rate_limited",
        detail,
        retryAfterSeconds: null,
      });
    },
  );

  it("says that the conversation ended for a 404", () => {
    const body = { detail: "This conversation has ended. Start a new one." };
    expect(failureFromResponse(404, null, body)).toEqual({ kind: "conversation_ended" });
  });

  it("gives the detail of another status when it is a text", () => {
    const body = { detail: "This conversation is busy. Wait for its answer." };
    expect(failureFromResponse(409, null, body)).toEqual({ kind: "http", message: body.detail });
  });

  it.each([
    [
      403,
      "The bot check did not pass. If you use an ad blocker or privacy extension, " +
        "allow challenges.cloudflare.com, then try again.",
    ],
    [503, "The bot check is not available. Try again in a few minutes."],
  ])("gives the text of a bot check refusal with %i", (status, detail) => {
    expect(failureFromResponse(status, null, { detail })).toEqual({
      kind: "http",
      message: detail,
    });
  });

  it.each([
    ["a list", { detail: [{ loc: ["body", "question"], msg: "too long" }] }],
    ["no detail", {}],
    ["no JSON body", null],
    ["a text body", "Bad Gateway"],
  ])("gives no message for a 422 with %s", (_name, body) => {
    expect(failureFromResponse(422, null, body)).toEqual({ kind: "http", message: null });
  });
});

describe("askStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the token of the bot check in the body", async () => {
    const fetch = vi.fn(async () => new Response(sse("answer", ANSWER_DATA)));
    vi.stubGlobal("fetch", fetch);
    const body = { question: "Shots?", turnstile_token: "token-1" };

    const events: AskEvent[] = [];
    for await (const event of askStream("http://api", body, new AbortController().signal)) {
      events.push(event);
    }

    expect(events.map((event) => event.type)).toEqual(["answer"]);
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api/api/ask");
    expect(JSON.parse(init.body as string)).toEqual(body);
  });
});
