"use client";

import { useEffect, useRef, useState } from "react";

import { AnswerPanel } from "@/components/ask/answer-panel";
import { AnswerSkeleton } from "@/components/ask/answer-skeleton";
import { FailureCard } from "@/components/ask/failure-card";
import { Landing } from "@/components/ask/landing";
import { QuestionBar } from "@/components/ask/question-bar";
import { QuestionHeading } from "@/components/ask/question-heading";
import { SiteHeader } from "@/components/ask/site-header";
import { StepList } from "@/components/ask/step-list";
import { useAsk } from "@/hooks/use-ask";
import { useSuggestions } from "@/hooks/use-suggestions";

/** The Ask the Analyst page: one question and its answer at a time. */
export function AskPage({ apiUrl }: { apiUrl: string }) {
  const suggestions = useSuggestions(apiUrl);
  const { state, ask, backToBar, reset } = useAsk(apiUrl);
  const titleRef = useRef<HTMLHeadingElement>(null);
  // The landing screen plays its enter motion until the first question.
  const [asked, setAsked] = useState(false);
  const questions = suggestions.status === "ready" ? suggestions.questions : [];

  // A screen reader and a keyboard start at the result, and the page scrolls
  // to it after a follow-up from the bar at the bottom.
  const settled = state.phase === "answered" || state.phase === "failed";
  useEffect(() => {
    if (settled) titleRef.current?.focus();
  }, [settled]);

  if (state.phase === "idle") {
    return (
      <Landing
        suggestions={suggestions}
        draft={state.draft}
        intro={!asked}
        onAsk={(question) => {
          setAsked(true);
          ask(question, { asNew: true });
        }}
      />
    );
  }

  return (
    <>
      <SiteHeader onNewQuestion={reset} />
      <main className="mx-auto flex w-full max-w-[1360px] flex-1 flex-col gap-8 px-4 pt-8 pb-16 sm:px-10 sm:pt-12">
        {state.phase === "asking" && (
          <>
            <QuestionHeading turn={state.turn} titleRef={titleRef} />
            <div className="flex flex-wrap items-start gap-8">
              <StepList
                steps={state.turn.steps}
                startedAt={state.turn.startedAt}
                onStop={backToBar}
              />
              <AnswerSkeleton />
            </div>
          </>
        )}

        {state.phase === "answered" && (
          <>
            <AnswerPanel
              turn={state.turn}
              data={state.data}
              endedAt={state.endedAt}
              titleRef={titleRef}
              suggestions={questions}
              onAsk={ask}
            />
            <QuestionBar
              label="Ask a follow-up"
              placeholder="e.g. Only the ones inside the box"
              onAsk={(question) => ask(question)}
            />
          </>
        )}

        {state.phase === "failed" && (
          <>
            <QuestionHeading turn={state.turn} titleRef={titleRef} />
            <FailureCard
              turn={state.turn}
              failure={state.failure}
              failedAt={state.endedAt}
              onRetry={() => ask(state.turn.question)}
              onAskAsNew={() => ask(state.turn.question, { asNew: true })}
              onEdit={backToBar}
            />
          </>
        )}
      </main>
    </>
  );
}
