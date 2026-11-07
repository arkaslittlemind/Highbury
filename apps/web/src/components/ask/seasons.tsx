import { CountUp } from "@/components/ask/count-up";
import { Reveal } from "@/components/ask/reveal";
import { SectionHead } from "@/components/ask/section-head";
import { SEASONS, type Season } from "@/lib/landing-content";
import { LANDING_DATA } from "@/lib/landing-data";
import { cn, keepSeasonsWhole } from "@/lib/utils";

function SeasonCard({ season, now = false }: { season: Season; now?: boolean }) {
  const { won, drawn, lost } = LANDING_DATA.records[season.label];
  return (
    <article
      className={cn(
        // One column that never grows past the card, whatever a row holds.
        "relative isolate grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_auto_auto_1fr_auto] gap-4.5 overflow-hidden rounded-[18px] p-8 max-[600px]:px-5 max-[600px]:py-6",
        // 2003-04 on paper; 2025-26 in the dark red of that season.
        now ? "border border-now-line bg-now-950 text-now-text" : "bg-paper text-paper-muted",
      )}
    >
      {/* The badge goes under the season when the two do not fit on one line. */}
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2.5">
        <h3
          className={cn(
            "font-display text-[clamp(36px,4vw,52px)] leading-[0.95] font-extrabold font-stretch-semi-expanded",
            now ? "text-brand" : "text-background",
          )}
        >
          {keepSeasonsWhole(season.label)}
        </h3>
        <span
          className={cn(
            "rounded-full px-2.5 py-1.75 font-mono text-xs leading-none font-medium tracking-[0.06em] whitespace-nowrap uppercase",
            now ? "bg-now-900 text-now-text" : "bg-background/8 text-paper-muted",
          )}
        >
          {season.source}
        </span>
      </div>
      <p
        className={cn(
          "font-display text-[19px] leading-[1.3] font-semibold font-stretch-semi-expanded italic",
          now ? "text-now-text" : "text-background",
        )}
      >
        {keepSeasonsWhole(season.line)}
      </p>
      {/* The record is read as one phrase; the numbers below count up for the eye. */}
      <p className="sr-only">{`Record: ${won} won, ${drawn} drawn, ${lost} lost.`}</p>
      <div aria-hidden="true" className="flex gap-7">
        {(
          [
            ["Won", won],
            ["Drawn", drawn],
            ["Lost", lost],
          ] as const
        ).map(([name, count]) => (
          <div key={name} className="grid gap-1.5">
            <b
              className={cn(
                "font-display text-[44px] leading-none font-extrabold max-[600px]:text-4xl",
                now ? "text-now-text" : "text-background",
              )}
            >
              <CountUp value={count} />
            </b>
            <span className="text-xs font-semibold tracking-[0.08em] uppercase">{name}</span>
          </div>
        ))}
      </div>
      <ul className="grid content-start gap-2.5 text-[15.5px] leading-[1.45]">
        {season.has.map((item) => (
          <li key={item} className="grid grid-cols-[18px_1fr] items-start gap-2.5">
            <span
              aria-hidden="true"
              className={cn(
                "text-[13px] leading-[1.6] font-bold",
                now ? "text-verified" : "text-verified-on-paper",
              )}
            >
              ✓
            </span>
            {item}
          </li>
        ))}
      </ul>
      <p
        className={cn(
          "rounded-[10px] border px-3.5 py-3 text-[14.5px] leading-normal",
          now
            ? "border-now-line bg-now-900 text-now-text"
            : "border-background/12 bg-background/6 text-paper-muted",
        )}
      >
        <b className={cn("font-semibold", now ? "text-brand" : "text-background")}>
          {season.note.lead}
        </b>{" "}
        {season.note.text}
      </p>
    </article>
  );
}

/** What each season can answer, and where it stops, with the record of each side. */
export function Seasons() {
  return (
    // The link in the header goes to this id.
    <section
      id="seasons"
      aria-labelledby="seasons-title"
      className="mx-auto w-full max-w-[1200px] scroll-mt-6 pb-30 max-[600px]:pb-22"
    >
      <SectionHead id="seasons-title" headline={SEASONS.headline} lead={SEASONS.lead} />
      <div className="grid grid-cols-2 gap-5 max-[760px]:grid-cols-1">
        <Reveal>
          <SeasonCard season={SEASONS.then} />
        </Reveal>
        <Reveal delay={70}>
          <SeasonCard season={SEASONS.now} now />
        </Reveal>
      </div>
      <p className="mx-auto mt-5 max-w-[64ch] text-center text-[15px] text-muted-foreground">
        {keepSeasonsWhole(SEASONS.note)}
      </p>
    </section>
  );
}
