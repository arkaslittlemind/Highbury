"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

// Next.js puts the value into the bundle at build time. A change needs a new build.
const API_URL = process.env.NEXT_PUBLIC_API_URL;

const UNREACHABLE = "The analyst API is not reachable.";
const UNEXPECTED = "Something went wrong. Try again.";

type Suggestion =
  | { state: "loading" }
  | { state: "ready"; question: string }
  | { state: "error"; message: string };

type Turn =
  | { state: "idle" }
  | { state: "asking"; steps: string[] }
  | { state: "answered"; steps: string[]; summary: string }
  | { state: "error"; steps: string[]; message: string };

type ServerEvent = { name: string; data: Record<string, unknown> };

function badStatus(status: number): string {
  return `The analyst API answered with status ${status}.`;
}

/** Read one server-sent event: an "event:" line, then a "data:" line of JSON. */
function parseEvent(block: string): ServerEvent {
  const [first = "", second = ""] = block.split("\n");
  if (!first.startsWith("event: ") || !second.startsWith("data: ")) {
    throw new Error("The event has a wrong form.");
  }
  return { name: first.slice(7), data: JSON.parse(second.slice(6)) };
}

async function loadSuggestion(signal: AbortSignal): Promise<Suggestion> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/suggestions`, { signal });
  } catch {
    // fetch rejects only when no response came.
    return { state: "error", message: UNREACHABLE };
  }
  if (!response.ok) {
    return { state: "error", message: badStatus(response.status) };
  }
  const body: { suggestions?: unknown } = await response.json();
  const first = Array.isArray(body.suggestions) ? body.suggestions[0] : null;
  if (typeof first !== "string") {
    return { state: "error", message: UNEXPECTED };
  }
  return { state: "ready", question: first };
}

/** Ask the question. Call onTurn each time the turn changes. */
async function ask(question: string, onTurn: (turn: Turn) => void) {
  const steps: string[] = [];
  onTurn({ state: "asking", steps });

  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    onTurn({ state: "error", steps, message: UNREACHABLE });
    return;
  }
  if (response.status === 429) {
    const body: { detail?: unknown } = await response.json();
    const message =
      typeof body.detail === "string" ? body.detail : badStatus(429);
    onTurn({ state: "error", steps, message });
    return;
  }
  if (!response.ok || !response.body) {
    onTurn({ state: "error", steps, message: badStatus(response.status) });
    return;
  }

  // A read gives a part of the stream, so an event can come in two parts.
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let end = buffer.indexOf("\n\n");
    while (end !== -1) {
      const { name, data } = parseEvent(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      end = buffer.indexOf("\n\n");
      if (name === "step") {
        steps.push(String(data.label));
        onTurn({ state: "asking", steps: [...steps] });
      } else if (name === "answer") {
        const answer = data.answer as { summary?: unknown };
        onTurn({ state: "answered", steps, summary: String(answer.summary) });
        return;
      } else if (name === "error") {
        onTurn({ state: "error", steps, message: String(data.message) });
        return;
      }
      // The chart event has no use on this page.
    }
  }
  onTurn({ state: "error", steps, message: UNEXPECTED });
}

/**
 * Shows that this page can reach the analyst API and that an answer streams.
 * It is temporary: the Ask page replaces it.
 */
export function ConnectionCheck() {
  const [suggestion, setSuggestion] = useState<Suggestion>({ state: "loading" });
  const [turn, setTurn] = useState<Turn>({ state: "idle" });

  useEffect(() => {
    if (!API_URL) return;
    const controller = new AbortController();
    loadSuggestion(controller.signal)
      .catch((): Suggestion => ({ state: "error", message: UNEXPECTED }))
      .then((loaded) => {
        if (!controller.signal.aborted) setSuggestion(loaded);
      });
    return () => controller.abort();
  }, []);

  if (!API_URL) {
    return (
      <p role="alert" className="text-destructive">
        NEXT_PUBLIC_API_URL is not set, so this page cannot reach the analyst
        API.
      </p>
    );
  }
  if (suggestion.state === "loading") {
    return <p className="text-muted-foreground">Connecting to the analyst…</p>;
  }
  if (suggestion.state === "error") {
    return (
      <p role="alert" className="text-destructive">
        {suggestion.message}
      </p>
    );
  }

  const { question } = suggestion;
  const steps = turn.state === "idle" ? [] : turn.steps;

  function start() {
    ask(question, setTurn).catch(() =>
      setTurn({ state: "error", steps: [], message: UNEXPECTED }),
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        The analyst API is reachable.
      </p>
      <p className="font-medium">{question}</p>
      <div>
        <Button onClick={start} disabled={turn.state === "asking"}>
          {turn.state === "asking" ? "Asking…" : "Ask"}
        </Button>
      </div>
      <div aria-live="polite" className="flex flex-col gap-2">
        {steps.length > 0 && (
          <ol className="list-decimal pl-5 text-sm text-muted-foreground">
            {steps.map((label, index) => (
              <li key={index}>{label}</li>
            ))}
          </ol>
        )}
        {turn.state === "answered" && <p>{turn.summary}</p>}
      </div>
      {turn.state === "error" && (
        <p role="alert" className="text-destructive">
          {turn.message}
        </p>
      )}
    </section>
  );
}
