import type {
  AnswerData,
  ChartSpec,
  Step,
  Verification,
  WorkingStep,
} from "@/lib/analyst-schema";
import type { AskEvent, AskFailure } from "@/lib/ask-stream";

/** One question and what came for it. Times are milliseconds of one clock. */
export type Turn = {
  question: string;
  // The question went out with a conversation id.
  followUp: boolean;
  steps: Step[];
  charts: ChartSpec[];
  startedAt: number;
};

export type AskState =
  // draft is the text that goes back into the question bar.
  | { phase: "idle"; conversationId: null; draft: string }
  | { phase: "asking"; conversationId: string | null; turn: Turn }
  | { phase: "answered"; conversationId: string; turn: Turn; data: AnswerData; endedAt: number }
  | {
      phase: "failed";
      conversationId: string | null;
      turn: Turn;
      failure: AskFailure;
      endedAt: number;
    };

export type AskAction =
  // asNew starts a conversation, also when the state holds an id.
  | { type: "ask"; question: string; asNew: boolean; now: number }
  | { type: "event"; event: AskEvent; now: number }
  // Stop and Edit question: back to the bar with the question in it.
  | { type: "back_to_bar" }
  | { type: "reset" };

export const INITIAL_STATE: AskState = { phase: "idle", conversationId: null, draft: "" };

// After these failures the service has no conversation to continue: an error
// ends it, a 404 says that it is gone, and a broken stream leaves its turn
// running, so the conversation is busy. The other failures come before the turn
// starts, and the conversation is as it was.
const ENDS_CONVERSATION: ReadonlySet<AskFailure["kind"]> = new Set([
  "agent",
  "conversation_ended",
  "unexpected",
]);

function onEvent(state: AskState, event: AskEvent, now: number): AskState {
  // An event can come after Stop. The page has left its turn.
  if (state.phase !== "asking") return state;
  const { turn } = state;
  switch (event.type) {
    case "step":
      return { ...state, turn: { ...turn, steps: [...turn.steps, event.step] } };
    case "chart":
      return { ...state, turn: { ...turn, charts: [...turn.charts, event.chart] } };
    case "answer":
      return {
        phase: "answered",
        conversationId: event.data.conversation_id,
        turn,
        data: event.data,
        endedAt: now,
      };
    case "failure":
      return {
        phase: "failed",
        conversationId: ENDS_CONVERSATION.has(event.failure.kind) ? null : state.conversationId,
        turn,
        failure: event.failure,
        endedAt: now,
      };
  }
}

export function reduce(state: AskState, action: AskAction): AskState {
  switch (action.type) {
    case "ask": {
      const conversationId = action.asNew ? null : state.conversationId;
      return {
        phase: "asking",
        conversationId,
        turn: {
          question: action.question,
          followUp: conversationId !== null,
          steps: [],
          charts: [],
          startedAt: action.now,
        },
      };
    }
    case "event":
      return onEvent(state, action.event, action.now);
    case "back_to_bar":
      // The turn of a stopped question still runs on the service, and its
      // conversation is busy until it ends. So the id goes.
      return {
        phase: "idle",
        conversationId: null,
        draft: state.phase === "idle" ? state.draft : state.turn.question,
      };
    case "reset":
      return INITIAL_STATE;
  }
}

/**
 * How a failed question can go again: in its conversation as it is ("same"),
 * as the start of a new one ("as_new"), or not at all.
 */
export function retryOffer(turn: Turn, failure: AskFailure): "same" | "as_new" | "none" {
  if (failure.kind === "conversation_ended") return "as_new";
  if (!ENDS_CONVERSATION.has(failure.kind)) return "same";
  // The conversation is gone. A follow-up means nothing without it.
  return turn.followUp ? "none" : "same";
}

export function badgeState(verification: Verification): "none" | "verified" | "partial" {
  const unbacked = verification.unbacked_numbers.length > 0;
  if (verification.checked === 0 && !unbacked) return "none";
  if (verification.passed === verification.checked && !unbacked) return "verified";
  return "partial";
}

/** The charts that an answer names, in its order. Null when no valid chart came for an id. */
export function chartsOfAnswer(
  refs: { id: string }[],
  charts: ChartSpec[],
): { id: string; chart: ChartSpec | null }[] {
  return refs.map(({ id }) => ({
    id,
    chart: charts.findLast((chart) => chart.id === id) ?? null,
  }));
}

/** The place in the working of the tool call with this id, from 0. Null when no call has it. */
export function workingRowOf(working: WorkingStep[], callId: string): number | null {
  const row = working.findIndex((step) => step.call_id === callId);
  return row === -1 ? null : row;
}

export function formatElapsed(milliseconds: number): string {
  return `${(Math.max(0, milliseconds) / 1000).toFixed(1)} s`;
}

/** The seconds until a rate-limited question can go again. Zero when it can. */
export function secondsLeft(retryAfterSeconds: number, failedAt: number, now: number): number {
  return Math.max(0, Math.ceil(retryAfterSeconds - (now - failedAt) / 1000));
}

export function formatCountdown(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
