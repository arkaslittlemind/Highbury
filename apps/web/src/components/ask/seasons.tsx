import { Check, CircleAlert, Minus } from "lucide-react";

import { Reveal } from "@/components/ask/reveal";
import { SectionTag } from "@/components/ask/section-tag";
import { cn } from "@/lib/utils";

type Season = {
  label: string;
  source: string;
  line: string;
  // What the season holds. The data catalog of the service is the source.
  has: string[];
  lacks?: string;
};

const THEN: Season = {
  label: "2003-04",
  source: "StatsBomb Open Data",
  line: "The Invincibles · 26 W 12 D 0 L",
  has: [
    "Shots with StatsBomb xG and coordinates",
    "Passes and pressures, with coordinates",
    "Player stats for each match and for the season",
  ],
};

const NOW: Season = {
  label: "2025-26",
  source: "Understat",
  line: "The current side, shot by shot",
  has: [
    "Shots with Understat xG and coordinates",
    "Player stats for each match and for the season",
  ],
  lacks: "No pass data. Highbury says so and offers a shot map.",
};

function SeasonCard({ season, now = false }: { season: Season; now?: boolean }) {
  return (
    <article
      className={cn(
        "relative flex h-full flex-col gap-4 overflow-hidden rounded-[20px] border p-6 sm:gap-4.5 sm:p-9",
        now
          ? "border-now-line bg-linear-170 from-now-900 via-now-950 via-55% to-surface-chart"
          : "border-line-mid bg-linear-170 from-grass-700 via-grass-850 via-60% to-surface-chart",
      )}
    >
      {!now && <div aria-hidden="true" className="absolute inset-0 mown [--mown:60px]" />}
      <div className="relative flex flex-wrap items-baseline justify-between gap-3">
        <h3
          className={cn(
            "font-display text-[44px] leading-none font-bold sm:text-[56px]",
            now && "text-brand-soft",
          )}
        >
          {season.label}
        </h3>
        <span className="rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 text-sm">
          {season.source}
        </span>
      </div>
      <p
        className={cn(
          "relative font-display text-[22px] font-medium italic sm:text-[26px]",
          now ? "text-now-text" : "text-on-grass",
        )}
      >
        {season.line}
      </p>
      <ul className="relative flex flex-col gap-2.5 text-[17px]">
        {season.has.map((item) => (
          <li key={item} className="flex gap-2.5">
            <Check
              aria-hidden="true"
              className="mt-1 size-4.5 shrink-0 text-verified"
              strokeWidth={2.6}
            />
            {item}
          </li>
        ))}
        {season.lacks && (
          <li className="flex gap-2.5 text-now-muted">
            <Minus aria-hidden="true" className="mt-1 size-4.5 shrink-0" strokeWidth={2.6} />
            {season.lacks}
          </li>
        )}
      </ul>
    </article>
  );
}

/** What each season can answer, and where it stops. */
export function Seasons() {
  return (
    <section
      id="seasons"
      aria-labelledby="seasons-title"
      className="flex scroll-mt-6 flex-col gap-6 pt-6 pb-12 sm:gap-8 sm:pb-18"
    >
      <Reveal className="flex flex-col gap-3">
        <SectionTag>Seasons</SectionTag>
        <h2
          id="seasons-title"
          className="font-display text-[40px] leading-none font-semibold text-balance sm:text-[64px]"
        >
          Two seasons. <em>Honest about the gaps.</em>
        </h2>
      </Reveal>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(420px,100%),1fr))] gap-4 sm:gap-5">
        <Reveal>
          <SeasonCard season={THEN} />
        </Reveal>
        <Reveal delay={70}>
          <SeasonCard season={NOW} now />
        </Reveal>
      </div>
      <Reveal>
        <p className="flex items-start gap-2.5 text-caveat-text">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-caveat" />
          A comparison of the two seasons uses only the metrics that both have, and says that
          the two xG models are different.
        </p>
      </Reveal>
    </section>
  );
}
