import { Lock, ShieldCheck, TextAlignStart, type LucideIcon } from "lucide-react";

import { Reveal } from "@/components/ask/reveal";
import { SectionTag } from "@/components/ask/section-tag";
import { cn } from "@/lib/utils";

const CARDS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: TextAlignStart,
    title: "Reads the catalog first",
    text: "The agent reads what each season holds before it writes a query, so it knows that 2025-26 has shots but no passes.",
  },
  {
    icon: Lock,
    title: "Queries read-only",
    text: "One SELECT in each call, checked by a parser and run as a read-only role with a 5-second timeout and a row limit.",
  },
  {
    icon: ShieldCheck,
    title: "Checks every number",
    text: "Plain code checks every number against the tool output that it cites. A claim with no support is removed before you see it.",
  },
];

/** The three things that make an answer one that a visitor can trust. */
export function HowItWorks() {
  return (
    // The link in the header goes to this id.
    <section
      id="how"
      aria-labelledby="how-title"
      className="flex scroll-mt-6 flex-col gap-8 pt-16 pb-12 sm:gap-10 sm:pt-24 sm:pb-18"
    >
      <Reveal className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex max-w-[640px] flex-col gap-3">
          <SectionTag>How it works</SectionTag>
          <h2
            id="how-title"
            className="font-display text-[40px] leading-none font-semibold sm:text-[64px]"
          >
            Not a chatbot. <em className="block">An analyst with receipts.</em>
          </h2>
        </div>
        <p className="max-w-[380px] text-[17px] text-foreground-2">
          Every answer shows the tools it called, the SQL it ran, and which numbers passed the
          check.
        </p>
      </Reveal>
      <ol className="grid grid-cols-[repeat(auto-fit,minmax(min(280px,100%),1fr))] gap-4 sm:gap-5">
        {CARDS.map(({ icon: Icon, title, text }, index) => {
          // The last card is the promise of the page, so it is the light one.
          const light = index === CARDS.length - 1;
          return (
            <li key={title} className="flex">
              <Reveal
                delay={index * 70}
                className={cn(
                  "flex flex-1 flex-col gap-4 rounded-[20px] p-6 sm:p-8",
                  light
                    ? "bg-paper text-background"
                    : "border bg-linear-160 from-grass-card to-surface-chart to-70%",
                )}
              >
                <span
                  className={cn(
                    "flex size-13 items-center justify-center rounded-full",
                    light ? "bg-background text-paper" : "bg-paper text-background",
                  )}
                >
                  <Icon aria-hidden="true" className="size-5.5" strokeWidth={2} />
                </span>
                <h3 className="font-display text-[28px] leading-[1.05] font-semibold sm:text-[32px]">
                  {title}
                </h3>
                <p className={light ? "text-paper-muted" : "text-foreground-2"}>{text}</p>
              </Reveal>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
