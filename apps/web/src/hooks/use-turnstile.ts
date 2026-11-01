"use client";

import { useCallback, useEffect, useRef } from "react";

import { waitForToken, type TokenWait } from "@/lib/turnstile";

export const TURNSTILE_SCRIPT =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

// The part of the Turnstile script that this page uses. The script defines it on
// window, and a package only for these types is not worth it.
type TurnstileOptions = {
  sitekey: string;
  execution: "execute";
  appearance: "interaction-only";
  callback: (token: string) => void;
  "error-callback": () => void;
  "expired-callback": () => void;
  "timeout-callback": () => void;
  "before-interactive-callback": () => void;
  "after-interactive-callback": () => void;
};

type Turnstile = {
  render: (container: HTMLElement, options: TurnstileOptions) => string | undefined;
  execute: (widgetId: string) => void;
  reset: (widgetId: string) => void;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

/**
 * One Turnstile widget for the page, and a fresh token for each question.
 *
 * With no site key the page renders no widget, and each question goes out with
 * no token: the API refuses it with a text that the page shows.
 */
export function useTurnstile(siteKey: string | undefined) {
  const container = useRef<HTMLDivElement>(null);
  const widget = useRef<string | null>(null);
  // The question that waits for a token. A new question ends the wait of the last one.
  const pending = useRef<TokenWait | null>(null);
  // Each token is good for one question, so the widget runs again for the next one.
  const used = useRef(false);
  // A question can come before the script loads. It runs when the script is there.
  const queued = useRef(false);
  // The script did not load, so no token can come until the page loads again.
  const failed = useRef(false);

  const execute = useCallback(() => {
    const turnstile = window.turnstile;
    if (!turnstile || !widget.current) {
      queued.current = true;
      return;
    }
    queued.current = false;
    if (used.current) turnstile.reset(widget.current);
    used.current = true;
    turnstile.execute(widget.current);
  }, []);

  const onScriptLoad = useCallback(() => {
    const turnstile = window.turnstile;
    if (!siteKey || !turnstile || !container.current || widget.current) return;
    const fail = () => pending.current?.settle(null);
    widget.current =
      turnstile.render(container.current, {
        sitekey: siteKey,
        execution: "execute",
        appearance: "interaction-only",
        callback: (token) => pending.current?.settle(token),
        "error-callback": fail,
        "expired-callback": fail,
        "timeout-callback": fail,
        "before-interactive-callback": () => pending.current?.pause(),
        "after-interactive-callback": () => pending.current?.resume(),
      }) ?? null;
    if (queued.current) execute();
  }, [execute, siteKey]);

  // An ad blocker can stop the script, most often before the first question. Each
  // question then goes out at once with no token, and the API says what to do.
  const onScriptError = useCallback(() => {
    failed.current = true;
    pending.current?.settle(null);
  }, []);

  useEffect(
    () => () => {
      if (widget.current) window.turnstile?.remove(widget.current);
      widget.current = null;
      pending.current?.settle(null);
    },
    [],
  );

  const getToken = useCallback(
    (onSlow: () => void): Promise<string | null> => {
      pending.current?.settle(null);
      if (!siteKey || failed.current) return Promise.resolve(null);
      const wait = waitForToken(onSlow);
      pending.current = wait;
      execute();
      return wait.token;
    },
    [execute, siteKey],
  );

  return { container, getToken, onScriptLoad, onScriptError };
}
