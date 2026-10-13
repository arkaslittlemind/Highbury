"use client";

import { useEffect, useState } from "react";

import { loadSuggestions } from "@/lib/ask-stream";

export type Suggestions =
  | { status: "loading" }
  | { status: "ready"; questions: string[] }
  | { status: "failed" };

/** The questions of the chips. The page works without them. */
export function useSuggestions(apiUrl: string): Suggestions {
  const [suggestions, setSuggestions] = useState<Suggestions>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    loadSuggestions(apiUrl, controller.signal).then((questions) => {
      if (controller.signal.aborted) return;
      setSuggestions(questions ? { status: "ready", questions } : { status: "failed" });
    });
    return () => controller.abort();
  }, [apiUrl]);

  return suggestions;
}
