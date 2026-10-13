import { ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { ShotMark } from "@/components/charts/shot-map";
import { PENALTY_AREA, PITCH_WIDTH, SIX_YARD_BOX, toPitchPoint } from "@/lib/pitch";
import { SAMPLE_SHOT_MAP } from "@/lib/sample-shots";
import { drawOrder, outcomeKind, shotRadius, summaryText } from "@/lib/shot-map";
import { cn } from "@/lib/utils";

// The enter motion of the hero. It plays only with data-intro on the section:
// the first view of the page. A visitor who comes back for a new question
// wants the bar at once.
const RISE =
  "fill-mode-both duration-700 ease-out-strong in-data-intro:animate-in in-data-intro:fade-in in-data-intro:slide-in-from-bottom-3";
// A mark of the picture lands on the grass after the text is in place.
const LAND =
  "origin-center fill-mode-both duration-500 ease-out-strong [transform-box:fill-box] in-data-intro:animate-in in-data-intro:fade-in in-data-intro:zoom-in-75";

/** The grass behind the hero. It is a picture: its lines and marks hold no data. */
function Grass() {
  return (
    <div aria-hidden="true" className="absolute inset-0 -z-10 hero-grass">
      <div className="absolute inset-0 mown" />
      <svg className="absolute inset-0 size-full opacity-55 mix-blend-overlay">
        <filter id="hero-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix values="0 0 0 0 0.6  0 0 0 0 0.9  0 0 0 0 0.5  0 0 0 0.9 0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#hero-grain)" />
      </svg>
      <div className="absolute -inset-20 hero-shadows" />
      <svg
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 size-full"
      >
        <filter id="hero-chalk">
          <feGaussianBlur stdDeviation="1.6" />
        </filter>
        <g
          filter="url(#hero-chalk)"
          strokeLinecap="round"
          className="fill-none stroke-[#F2F5EE]/78"
        >
          <path d="M-40 838 L1480 668" strokeWidth="13" />
          <path d="M760 752 L1180 520" strokeWidth="9" />
          <path d="M1180 520 L1480 492" strokeWidth="7" />
          <path d="M928 660 C 990 690, 1090 680, 1150 640" strokeWidth="7" />
        </g>
        {/* The marks are above the place of the sample card at each width. On a
            narrow screen they are behind the text, so they are not drawn. */}
        <g className="max-lg:hidden">
          <ellipse cx="1000" cy="515" rx="34" ry="13" className="fill-black/28" />
          <ellipse
            cx="996"
            cy="505"
            rx="30"
            ry="12"
            strokeWidth="2"
            className={cn(LAND, "fill-brand stroke-background delay-[450ms]")}
          />
          <ellipse
            cx="1092"
            cy="480"
            rx="20"
            ry="8"
            strokeWidth="2"
            className={cn(LAND, "fill-brand stroke-background delay-[520ms]")}
          />
          <ellipse
            cx="900"
            cy="545"
            rx="16"
            ry="6.5"
            strokeWidth="3"
            className={cn(LAND, "fill-none stroke-paper delay-[590ms]")}
          />
          <ellipse
            cx="1150"
            cy="509"
            rx="13"
            ry="5.5"
            strokeWidth="3"
            className={cn(LAND, "fill-none stroke-paper delay-[660ms]")}
          />
          <path
            d="M1040 555 l14 -24 l14 24 z"
            strokeWidth="3"
            strokeLinejoin="round"
            className={cn(LAND, "fill-none stroke-foreground-2 delay-[730ms]")}
          />
          {/* The xG of the first goal of the sample chart. */}
          <g className={cn(RISE, "delay-[900ms]")}>
            <rect
              x="1020"
              y="425"
              width="126"
              height="30"
              rx="15"
              className="fill-background/60 stroke-white/22"
            />
            <text
              x="1083"
              y="444.5"
              textAnchor="middle"
              className="fill-paper font-mono text-xs"
            >
              Goal · xG 0.31
            </text>
          </g>
        </g>
      </svg>
      <div className="absolute inset-0 hero-shade" />
    </div>
  );
}

const CENTRE = PITCH_WIDTH / 2;
const AREA_LINE = { strokeWidth: 1, vectorEffect: "non-scaling-stroke" } as const;
const PROOFS = [
  "Read-only SQL",
  "Every claim traced to data",
  "Chart from a validated spec",
  "Honest when data is missing",
];

/** A small copy of an answer: the sample chart, and what the page promises for each answer. */
function SampleCard({ className }: { className?: string }) {
  const shots = SAMPLE_SHOT_MAP.shots;
  const goals = shots.filter((shot) => outcomeKind(shot.outcome) === "goal").length;
  return (
    <aside
      aria-label="Sample answer"
      className={cn("w-full max-w-[400px] overflow-hidden rounded-[14px] shadow-float", className)}
    >
      <div className="flex items-center justify-between gap-3 bg-paper px-5 py-3.5 text-background">
        <span className="font-bold">Checked answer</span>
        <span className="flex items-center gap-1.5 font-bold text-verified-on-paper">
          <ShieldCheck aria-hidden="true" className="size-4" strokeWidth={2.4} />
          {goals} goals · {shots.length} shots
        </span>
      </div>
      <div className="flex gap-5 rounded-b-[14px] border border-t-0 border-white/16 bg-[#0C1E12]/55 p-5 backdrop-blur-lg">
        <div className="flex w-[132px] shrink-0 flex-col gap-1.5">
          <span className="font-display text-lg leading-tight font-semibold text-on-grass italic">
            Henry v Liverpool
          </span>
          {/* The penalty area of the sample chart. */}
          <svg role="img" aria-label={summaryText(shots)} viewBox="14 -2 52 30" className="block w-full">
            <g className="fill-none stroke-white/45">
              <rect x="0" y="0" width={PITCH_WIDTH} height="60" className="fill-white/4" {...AREA_LINE} />
              <rect
                x={CENTRE - PENALTY_AREA.width / 2}
                y="0"
                width={PENALTY_AREA.width}
                height={PENALTY_AREA.depth}
                {...AREA_LINE}
              />
              <rect
                x={CENTRE - SIX_YARD_BOX.width / 2}
                y="0"
                width={SIX_YARD_BOX.width}
                height={SIX_YARD_BOX.depth}
                {...AREA_LINE}
              />
            </g>
            {drawOrder(shots).map((shot) => {
              const point = toPitchPoint(shot.x, shot.y);
              return (
                <g key={`${shot.x} ${shot.y}`} transform={`translate(${point.x} ${point.y})`}>
                  <ShotMark kind={outcomeKind(shot.outcome)} r={shotRadius(shot.xg)} />
                </g>
              );
            })}
          </svg>
          <span className="text-xs text-on-grass-muted">9 April 2004 · StatsBomb</span>
        </div>
        <ul className="flex flex-col justify-center gap-2.5 font-display text-[17px] leading-tight font-medium italic">
          {PROOFS.map((proof) => (
            <li key={proof} className="flex items-center gap-2.5">
              <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-paper" />
              {proof}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

type HeroProps = {
  // The first view of the page plays the enter motion.
  intro: boolean;
  // The question bar.
  children: ReactNode;
};

/** The top of the first screen: what Highbury is, and the bar to ask it. */
export function Hero({ intro, children }: HeroProps) {
  return (
    <section
      aria-labelledby="hero-title"
      data-intro={intro ? "" : undefined}
      className="relative isolate overflow-hidden"
    >
      <Grass />
      {/* The top padding is the room of the header, which lies on the hero. */}
      <div className="mx-auto grid min-h-[min(900px,100svh)] w-full max-w-[1280px] gap-10 px-4 pt-27 pb-10 sm:px-10 sm:pt-36 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-12 lg:pb-0">
        <div className="flex max-w-[700px] flex-col gap-5 self-center sm:gap-6.5 lg:pb-15">
          <p
            className={cn(
              RISE,
              "flex items-center gap-2.5 self-start rounded-full border border-white/20 bg-white/8 px-4 py-2 text-sm backdrop-blur-md sm:px-4.5 sm:text-[15px]",
            )}
          >
            <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-brand" />
            <span>
              The Invincibles <span aria-hidden="true">↔</span>
              <span className="sr-only">and</span> 2025-26 · an AI football analyst
            </span>
          </p>
          <h1
            id="hero-title"
            className={cn(
              RISE,
              "font-display text-[clamp(52px,7.2vw,104px)] leading-[0.95] font-semibold text-balance delay-[60ms]",
            )}
          >
            Two Arsenal eras.
            <br />
            <em>Every number checked.</em>
          </h1>
          <p
            className={cn(
              RISE,
              "max-w-[520px] text-lg leading-[1.55] text-on-grass delay-[120ms] sm:text-xl",
            )}
          >
            Ask in plain English. Highbury queries the data, draws the pitch chart, and checks
            every number before you see it. When the data cannot answer, it says so.
          </p>
          <div className={cn(RISE, "mt-1.5 max-w-[620px] delay-[180ms]")}>{children}</div>
          <div className={cn(RISE, "flex items-center gap-3 delay-[240ms]")}>
            <div
              aria-hidden="true"
              className="flex font-display text-[15px] font-extrabold *:flex *:size-11 *:items-center *:justify-center *:rounded-full *:border-2 *:not-first:-ml-3"
            >
              <span className="border-grass-800 bg-paper text-background">03</span>
              <span className="border-grass-800 bg-primary text-primary-foreground">26</span>
              <span className="border-white/35 bg-background/60 font-mono text-[11px] font-normal text-paper">
                SQL
              </span>
            </div>
            <p className="text-[15px] leading-[1.3] text-on-grass">
              Two seasons
              <br />
              Read-only data
            </p>
          </div>
        </div>
        <SampleCard className={cn(RISE, "delay-[320ms] lg:mb-18 lg:self-end")} />
      </div>
    </section>
  );
}
