"use client";

import { useEffect, useRef } from "react";

// The key in history.state that marks the entry of the answer screen. Next.js
// copies its own keys into the state of each pushState, so the entry stays its own.
const MARK = "highburyAnswer";

function onAnswerEntry(): boolean {
  return window.history.state?.[MARK] === true;
}

/**
 * Give the answer screen one browser history entry, so Back returns to the
 * landing page. The page keeps one answer at a time, so a follow-up adds no entry.
 */
export function useAnswerHistory(onLanding: boolean, backToLanding: () => void) {
  // The screen of the last render, for the popstate handler too.
  const landing = useRef(onLanding);

  useEffect(() => {
    const wasLanding = landing.current;
    landing.current = onLanding;
    if (wasLanding === onLanding) return;
    if (!onLanding) {
      // After Back, then Forward, the current entry has the mark already. A
      // new entry on top of it would make Back stop on a dead step.
      if (onAnswerEntry()) window.history.replaceState({ [MARK]: true }, "");
      else window.history.pushState({ [MARK]: true }, "");
    } else if (onAnswerEntry()) {
      // The page's own controls went back to the landing page: remove the entry,
      // so a later Back leaves the page.
      window.history.back();
    }
  }, [onLanding]);

  useEffect(() => {
    function onPopState() {
      if (!landing.current && !onAnswerEntry()) backToLanding();
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [backToLanding]);
}
