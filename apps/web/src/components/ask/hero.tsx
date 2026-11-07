import Image from "next/image";
import type { CSSProperties, ReactNode } from "react";

import seasonsPainting from "@/assets/seasons-painting.webp";
import { Pitch } from "@/components/charts/pitch";
import { ShotMark } from "@/components/charts/shot-map";
import { HERO } from "@/lib/landing-content";
import { toPitchPoint } from "@/lib/pitch";
import { SAMPLE_SHOT_MAP } from "@/lib/sample-shots";
import {
  OUTCOME_LABELS,
  drawOrder,
  outcomeKind,
  shotClaims,
  shotRadius,
  summaryText,
  type OutcomeKind,
} from "@/lib/shot-map";
import { cn, keepSeasonsWhole } from "@/lib/utils";

// The enter motion of the hero. It plays only with data-intro on the section:
// the first view of the page. A visitor who comes back for a new question
// wants the bar at once. Each part rises a little, in order, and the sample
// card lifts in last from further down. With reduced motion, the global rule
// in globals.css takes the movement out, so each part only fades.
const RISE =
  "fill-mode-both duration-[640ms] ease-out-strong in-data-intro:animate-in in-data-intro:fade-in in-data-intro:slide-in-from-bottom-3";
const LIFT =
  "fill-mode-both duration-[900ms] ease-out-strong in-data-intro:animate-in in-data-intro:fade-in in-data-intro:slide-in-from-bottom-[40px]";
// The step between two parts. Short, so the hero is complete in under a second.
const STAGGER_MS = 60;

function order(index: number): CSSProperties {
  return { animationDelay: `${index * STAGGER_MS}ms` };
}

/**
 * The painting behind the hero: old Highbury on the left and the Emirates on the
 * right, the two eras of the headline. It is decorative. The shade keeps the
 * text readable and fades the painting into the page at the bottom.
 */
function Painting() {
  return (
    <div aria-hidden="true" className="absolute inset-0 -z-10">
      <Image
        src={seasonsPainting}
        alt=""
        fill
        loading="eager"
        sizes="100vw"
        className="object-cover object-[50%_70%]"
      />
      <div className="absolute inset-0 hero-painting-shade" />
    </div>
  );
}

// The legend of the card, in the order of the chart. The outcome is the shape.
const LEGEND: OutcomeKind[] = ["goal", "saved", "blocked", "off_target"];

/** A checked answer, as the page draws one: the sample chart and the numbers that passed the check. */
function SampleCard() {
  const shots = SAMPLE_SHOT_MAP.shots;
  const claims = shotClaims(shots);
  const [goals, total] = claims;
  return (
    <aside aria-label="Sample answer" className="overflow-hidden rounded-[14px] shadow-float">
      <div className="flex items-center justify-between gap-3 bg-paper px-4.5 py-3 text-sm text-paper-muted">
        <strong className="font-semibold text-background">Checked answer</strong>
        <span className="font-bold text-verified-on-paper">
          {goals.value} goals · {total.value} shots
        </span>
      </div>
      <div className="grid items-start gap-5 rounded-b-[14px] border border-t-0 border-white/12 bg-grass-card/88 p-5 backdrop-blur-md sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div>
          <p className="mb-2 font-display text-[17px] leading-tight font-semibold font-stretch-semi-expanded italic">
            Henry v Liverpool
          </p>
          <Pitch view="attacking-half" role="img" aria-label={summaryText(shots)} className="rounded-lg">
            {drawOrder(shots).map((shot) => {
              const point = toPitchPoint(shot.x, shot.y);
              return (
                <g key={`${shot.x} ${shot.y}`} transform={`translate(${point.x} ${point.y})`}>
                  <ShotMark kind={outcomeKind(shot.outcome)} r={shotRadius(shot.xg)} />
                </g>
              );
            })}
          </Pitch>
          <ul
            aria-label="Legend"
            className="mt-2.5 flex flex-wrap gap-x-3.5 gap-y-1 text-xs text-on-grass-muted"
          >
            {LEGEND.map((kind) => (
              <li key={kind} className="flex items-center gap-1.5">
                <svg aria-hidden="true" viewBox="-6 -6 12 12" className="size-2.5 overflow-visible">
                  <ShotMark kind={kind} r={4} />
                </svg>
                {OUTCOME_LABELS[kind]}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-on-grass-muted">9 April 2004 · StatsBomb Open Data</p>
        </div>
        <div className="grid content-start gap-3.5">
          <p className="text-[15px] text-on-grass-muted">
            You asked{" "}
            <q className="text-foreground">Show Henry&apos;s shots in the 4-2 win over Liverpool.</q>
          </p>
          <span className="inline-flex items-center gap-2 justify-self-start rounded-full border border-verified-line bg-verified-bg py-1.5 pr-3 pl-2.5 text-sm font-semibold text-verified">
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="size-4 fill-none stroke-current"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
            {claims.length} of {claims.length} numbers checked
          </span>
          <ul>
            {claims.map(({ label, value }) => (
              <li
                key={label}
                className="flex justify-between gap-4 border-t border-white/10 py-2.5 text-[15px] text-on-grass"
              >
                {label}
                <b className="font-display text-lg leading-none font-bold tabular-nums">{value}</b>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  );
}

type HeroProps = {
  // The first view of the page plays the enter motion.
  intro: boolean;
  // The question bar.
  bar: ReactNode;
  // The example questions under the bar. Null when they did not load.
  chips: ReactNode;
};

/** The top of the first screen: what Highbury is, the bar to ask it, and a checked answer below. */
export function Hero({ intro, bar, chips }: HeroProps) {
  return (
    <section
      aria-labelledby="hero-title"
      data-intro={intro ? "" : undefined}
      className="relative isolate overflow-hidden"
    >
      <Painting />
      {/* The top padding holds the header, which lies on the hero. */}
      <div className="mx-auto max-w-[1200px] px-gutter pt-34 sm:pt-46">
        <div className="flex flex-col items-center gap-5 pb-10 text-center sm:gap-6 sm:pb-16">
          <h1
            id="hero-title"
            style={order(1)}
            className={cn(
              RISE,
              "font-display text-[clamp(36px,5vw,68px)] leading-[1.02] font-semibold tracking-[-0.01em] font-stretch-semi-expanded text-balance",
            )}
          >
            {HERO.headline[0]}
            <em className="block">{HERO.headline[1]}</em>
          </h1>
          <p
            style={order(2)}
            className={cn(RISE, "max-w-[46ch] text-[17px] leading-[1.55] text-on-grass sm:text-[19px]")}
          >
            {keepSeasonsWhole(HERO.intro)}
          </p>
          <div style={order(3)} className={cn(RISE, "mt-2 w-full max-w-[640px]")}>
            {bar}
          </div>
          {chips && (
            <div style={order(4)} className={cn(RISE, "w-full max-w-[880px]")}>
              {chips}
            </div>
          )}
        </div>
        {/* The card is cut at the bottom of the hero: the answer goes on below the fold. */}
        <div
          style={order(5)}
          className={cn(
            LIFT,
            "mx-auto h-[300px] w-full max-w-[860px] overflow-hidden sm:h-[360px]",
          )}
        >
          <SampleCard />
        </div>
      </div>
      {/* The painting and the card fade into the page together, so the hero has no edge. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[140px] bg-linear-to-b from-transparent to-background"
      />
    </section>
  );
}
