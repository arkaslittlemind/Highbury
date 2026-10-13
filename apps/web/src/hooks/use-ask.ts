"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { INITIAL_STATE, reduce, type AskAction, type AskState } from "@/lib/ask-state";
import { askStream } from "@/lib/ask-stream";

/** One turn with the analyst at a time, and the conversation it belongs to. */
export function useAsk(apiUrl: string) {
  const [state, setState] = useState<AskState>(INITIAL_STATE);
  // The request needs the conversation id of the state after the "ask" action,
  // in the same call. State from useState comes only with the next render.
  const current = useRef<AskState>(INITIAL_STATE);
  const request = useRef<AbortController | null>(null);

  const apply = useCallback((action: AskAction) => {
    current.current = reduce(current.current, action);
    setState(current.current);
  }, []);

  const abort = useCallback(() => {
    request.current?.abort();
    request.current = null;
  }, []);

  useEffect(() => abort, [abort]);

  const ask = useCallback(
    (question: string, options: { asNew?: boolean } = {}) => {
      const trimmed = question.trim();
      if (!trimmed) return;
      abort();
      const controller = new AbortController();
      request.current = controller;
      apply({
        type: "ask",
        question: trimmed,
        asNew: options.asNew ?? false,
        now: performance.now(),
      });
      const conversationId = current.current.conversationId;

      async function run() {
        const events = askStream(
          apiUrl,
          { question: trimmed, ...(conversationId && { conversation_id: conversationId }) },
          controller.signal,
        );
        for await (const event of events) {
          if (controller.signal.aborted) return;
          apply({ type: "event", event, now: performance.now() });
        }
      }

      run().catch(() => {
        // The stream client gives each known failure as an event. An error
        // here is one that it does not know.
        if (controller.signal.aborted) return;
        apply({
          type: "event",
          event: { type: "failure", failure: { kind: "unexpected" } },
          now: performance.now(),
        });
      });
    },
    [abort, apiUrl, apply],
  );

  const backToBar = useCallback(() => {
    abort();
    apply({ type: "back_to_bar" });
  }, [abort, apply]);

  const reset = useCallback(() => {
    abort();
    apply({ type: "reset" });
  }, [abort, apply]);

  return { state, ask, backToBar, reset };
}
