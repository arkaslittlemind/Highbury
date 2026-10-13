import {
  answerDataSchema,
  chartSpecSchema,
  errorDataSchema,
  stepSchema,
  suggestionsSchema,
  type AnswerData,
  type ChartSpec,
  type Step,
} from "@/lib/analyst-schema";

/** Why a turn gave no answer. */
export type AskFailure =
  // The error event of the service. Its text is safe to show.
  | { kind: "agent"; message: string }
  | { kind: "unreachable" }
  | { kind: "rate_limited"; detail: string; retryAfterSeconds: number | null }
  | { kind: "conversation_ended" }
  // Any other status. The message is the detail of the body when it is a text.
  | { kind: "http"; message: string | null }
  | { kind: "unexpected" };

export type AskEvent =
  | { type: "step"; step: Step }
  | { type: "chart"; chart: ChartSpec }
  | { type: "answer"; data: AnswerData }
  | { type: "failure"; failure: AskFailure };

export type AskBody = { question: string; conversation_id?: string };

const UNEXPECTED: AskEvent = { type: "failure", failure: { kind: "unexpected" } };

/** Read one server-sent event: an "event:" line, then a "data:" line of JSON. */
function parseEvent(block: string): AskEvent | "skip" {
  const [first = "", second = ""] = block.split("\n");
  if (!first.startsWith("event: ") || !second.startsWith("data: ")) return UNEXPECTED;
  let data: unknown;
  try {
    data = JSON.parse(second.slice(6));
  } catch {
    return UNEXPECTED;
  }
  switch (first.slice(7)) {
    case "step": {
      const step = stepSchema.safeParse(data);
      return step.success ? { type: "step", step: step.data } : UNEXPECTED;
    }
    case "chart": {
      // A chart that fails its schema does not end the turn. The answer still
      // names its id, and the page shows a fallback for it.
      const chart = chartSpecSchema.safeParse(data);
      return chart.success ? { type: "chart", chart: chart.data } : "skip";
    }
    case "answer": {
      const answer = answerDataSchema.safeParse(data);
      return answer.success ? { type: "answer", data: answer.data } : UNEXPECTED;
    }
    case "error": {
      const error = errorDataSchema.safeParse(data);
      return error.success
        ? { type: "failure", failure: { kind: "agent", message: error.data.message } }
        : UNEXPECTED;
    }
    default:
      // An event that this page does not know is not an error.
      return "skip";
  }
}

/**
 * Turn the text of a stream into events. The last event is always an answer or
 * a failure, also when the stream is cut.
 */
export async function* readEvents(chunks: AsyncIterable<string>): AsyncGenerator<AskEvent> {
  // A read gives a part of the stream, so an event can come in two parts.
  let buffer = "";
  for await (const chunk of chunks) {
    buffer += chunk;
    let end = buffer.indexOf("\n\n");
    while (end !== -1) {
      const event = parseEvent(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      end = buffer.indexOf("\n\n");
      if (event === "skip") continue;
      yield event;
      if (event.type === "answer" || event.type === "failure") return;
    }
  }
  yield UNEXPECTED;
}

/** Name the failure of a response that is not OK. */
export function failureFromResponse(
  status: number,
  retryAfter: string | null,
  body: unknown,
): AskFailure {
  const detail =
    typeof body === "object" && body !== null && "detail" in body ? body.detail : null;
  const message = typeof detail === "string" ? detail : null;
  if (status === 429) {
    const seconds = retryAfter === null ? NaN : Number(retryAfter);
    return {
      kind: "rate_limited",
      detail: message ?? "Too many questions. Try again in a minute.",
      retryAfterSeconds: Number.isInteger(seconds) && seconds > 0 ? seconds : null,
    };
  }
  if (status === 404) return { kind: "conversation_ended" };
  return { kind: "http", message };
}

async function* textChunks(body: NonNullable<Response["body"]>): AsyncGenerator<string> {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    yield value;
  }
}

/**
 * Ask one question and give the events of its turn. After an abort it gives no
 * more events.
 */
export async function* askStream(
  apiUrl: string,
  body: AskBody,
  signal: AbortSignal,
): AsyncGenerator<AskEvent> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    // fetch rejects only when no response came, or on an abort.
    if (!signal.aborted) yield { type: "failure", failure: { kind: "unreachable" } };
    return;
  }
  if (!response.ok) {
    // The body of an error is JSON from the service, but a proxy can send HTML.
    const errorBody: unknown = await response.json().catch(() => null);
    yield {
      type: "failure",
      failure: failureFromResponse(
        response.status,
        response.headers.get("Retry-After"),
        errorBody,
      ),
    };
    return;
  }
  if (!response.body) {
    yield UNEXPECTED;
    return;
  }
  try {
    yield* readEvents(textChunks(response.body));
  } catch {
    // A read fails when the connection drops, or on an abort.
    if (!signal.aborted) yield UNEXPECTED;
  }
}

/** Load the questions of the chips. Null when the service gives none. */
export async function loadSuggestions(
  apiUrl: string,
  signal: AbortSignal,
): Promise<string[] | null> {
  try {
    const response = await fetch(`${apiUrl}/api/suggestions`, { signal });
    if (!response.ok) return null;
    const body = suggestionsSchema.safeParse(await response.json());
    return body.success ? body.data.suggestions : null;
  } catch {
    return null;
  }
}
