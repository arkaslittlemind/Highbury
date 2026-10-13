import type { ReactNode } from "react";

import { Reveal } from "@/components/ask/reveal";

/** The last panel of the landing screen: the question bar again, for a visitor who read to the end. */
export function ClosingAsk({ children }: { children: ReactNode }) {
  return (
    <Reveal className="mb-12 sm:mb-18">
      <section
        aria-labelledby="closing-title"
        className="relative isolate overflow-hidden rounded-[28px] bg-linear-to-b from-grass-800 to-grass-500 px-5 py-10 sm:px-14 sm:py-16"
      >
        <div aria-hidden="true" className="absolute inset-0 -z-10 mown [--mown:90px]">
          <svg
            viewBox="0 0 1200 360"
            preserveAspectRatio="none"
            className="absolute inset-0 size-full fill-none stroke-[#F2F5EE]"
          >
            <path d="M-20 330 L1220 250" strokeOpacity="0.5" strokeWidth="8" />
            <path d="M880 270 C 940 300, 1050 290, 1110 255" strokeOpacity="0.4" strokeWidth="5" />
          </svg>
        </div>
        <div className="flex max-w-[760px] flex-col gap-6">
          <h2
            id="closing-title"
            className="font-display text-[40px] leading-[0.98] font-semibold text-balance sm:text-[72px]"
          >
            What do you want to know <em>about these two sides?</em>
          </h2>
          {children}
        </div>
      </section>
    </Reveal>
  );
}
