"use client";

import { useRef, useState } from "react";

import { AskPill } from "@/components/ask/ask-pill";
import { Capabilities } from "@/components/ask/capabilities";
import { ClosingAsk } from "@/components/ask/closing-ask";
import { Gallery } from "@/components/ask/gallery";
import { Hero } from "@/components/ask/hero";
import { ProofBand } from "@/components/ask/proof-band";
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

// On a phone the chips are one row that scrolls in its own box. The row runs
// to the edge of the screen, so a cut chip shows that there are more.
const CHIP_ROW =
  "min-h-target sm:min-h-[98px] max-[600px]:-mr-gutter max-[600px]:w-[calc(100%+var(--spacing-gutter))]";
// The chips lie on the grass, as glass, like the bar above them.
const CHIP =
  "border-white/16 bg-[rgb(10_18_14/0.35)] text-sm text-on-grass hover:border-white/40 hover:bg-[rgb(10_18_14/0.6)] max-[600px]:flex-none max-[600px]:whitespace-nowrap";

/** The screen before a question: what Highbury is, why its numbers hold, and the bar to ask it. */
export function Landing({ suggestions, draft, intro, onAsk }: LandingProps) {
  const bar = useRef<HTMLInputElement>(null);
  // The text of the hero bar. A Try link of a capability card sets it.
  const [question, setQuestion] = useState(draft);

  // A Try link puts its question into the hero bar and moves the visitor there. The
  // scroll is smooth unless the visitor asks for reduced motion (scroll-behavior in
  // globals.css), and the focus must not jump the page.
  function fillBar(text: string) {
    setQuestion(text);
    bar.current?.scrollIntoView({ block: "center" });
    bar.current?.focus({ preventScroll: true });
  }
  const questions = suggestions.status === "ready" ? suggestions.questions : [];
  const [first] = questions;

  return (
    // The header lies on the hero, so that the two have one piece of grass.
    <div className="relative flex flex-1 flex-col">
      <SiteHeader onAsk={() => bar.current?.focus()} />
      <main>
        <Hero
          intro={intro}
          bar={
            <AskPill
              label="Ask the Analyst"
              placeholder="e.g. Show me Thierry Henry's shots in 2003-04"
              initialQuestion={draft}
              value={question}
              onValueChange={setQuestion}
              inputRef={bar}
              onAsk={onAsk}
            />
          }
          chips={
            // The row has its place before the chips come, so the card below it does not jump.
            suggestions.status !== "failed" && (
              <div className={CHIP_ROW}>
                <SuggestionChips
                  questions={questions}
                  onPick={onAsk}
                  stagger
                  className="justify-center max-[600px]:flex-nowrap max-[600px]:justify-start max-[600px]:overflow-x-auto max-[600px]:pr-gutter max-[600px]:[scrollbar-width:none]"
                  chipClassName={CHIP}
                />
              </div>
            )
          }
        />
        <div className="mx-auto flex w-full max-w-[1360px] flex-col px-4 sm:px-10">
          <Capabilities onTry={fillBar} />
          <Seasons />
          <Gallery onTry={fillBar} />
          <ProofBand />
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
