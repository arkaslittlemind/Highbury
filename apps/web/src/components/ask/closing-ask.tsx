import type { ReactNode } from "react";

import { Reveal } from "@/components/ask/reveal";

/**
 * The last ask of the landing screen, after the FAQ: the question bar again, for a
 * visitor who read to the end. It sits on the page background with no panel, so
 * the FAQ, this ask, and the footer read as one area.
 */
export function ClosingAsk({ children }: { children: ReactNode }) {
  return (
    <Reveal className="pb-24 max-[600px]:pb-18">
      <section
        aria-labelledby="closing-title"
        className="mx-auto flex w-full max-w-[760px] flex-col items-center gap-7 text-center"
      >
        <h2
          id="closing-title"
          className="font-display text-[32px] leading-[1.02] font-semibold font-stretch-semi-expanded text-balance sm:text-[52px]"
        >
          What do you want to know <em>about these two sides?</em>
        </h2>
        <div className="w-full max-w-[640px]">{children}</div>
      </section>
    </Reveal>
  );
}
