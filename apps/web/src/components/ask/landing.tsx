"use client";

import { useRef } from "react";

import { AskPill } from "@/components/ask/ask-pill";
import { ClosingAsk } from "@/components/ask/closing-ask";
import { Hero } from "@/components/ask/hero";
import { HowItWorks } from "@/components/ask/how-it-works";
import { SampleAnswer } from "@/components/ask/sample-answer";
import { Seasons } from "@/components/ask/seasons";
import { SiteHeader } from "@/components/ask/site-header";
import { SuggestionChips } from "@/components/ask/suggestion-chips";
import type { Suggestions } from "@/hooks/use-suggestions";

type LandingProps = {
  suggestions: Suggestions;
  // The text that goes back into the question bar.
  draft: string;
  // The first view of the page plays the enter motion of the hero.
  intro: boolean;
  onAsk: (question: string) => void;
};

/** The screen before a question: what Highbury is, why its numbers hold, and the bar to ask it. */
export function Landing({ suggestions, draft, intro, onAsk }: LandingProps) {
  const bar = useRef<HTMLInputElement>(null);
  const questions = suggestions.status === "ready" ? suggestions.questions : [];
  const [first] = questions;

  return (
    // The header lies on the hero, so that the two have one piece of grass.
    <div className="relative flex flex-1 flex-col">
      <SiteHeader onAsk={() => bar.current?.focus()} />
      <main>
        <Hero intro={intro}>
          <AskPill
            label="Ask the Analyst"
            placeholder="e.g. Show me Thierry Henry's shots in 2003-04"
            initialQuestion={draft}
            inputRef={bar}
            onAsk={onAsk}
          />
        </Hero>
        <div className="mx-auto flex w-full max-w-[1360px] flex-col px-4 sm:px-10">
          {/* The row has its place before the chips come, so the page below it does not jump. */}
          {suggestions.status !== "failed" && (
            <section
              aria-label="Example questions"
              className="flex min-h-27 items-center border-b py-7 sm:min-h-29 sm:py-9"
            >
              <SuggestionChips lead="Try asking" questions={questions} onPick={onAsk} stagger />
            </section>
          )}
          <HowItWorks />
          <Seasons />
          <SampleAnswer onSeeAnswer={first ? () => onAsk(first) : undefined} />
          <ClosingAsk>
            <AskPill
              label="Your question"
              placeholder="e.g. Compare Henry and Saka on goals per 90"
              onAsk={onAsk}
            />
          </ClosingAsk>
        </div>
      </main>
    </div>
  );
}
