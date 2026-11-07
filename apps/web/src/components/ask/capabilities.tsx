"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent,
  type ReactNode,
} from "react";

import styles from "@/components/ask/capabilities.module.css";
import { Reveal } from "@/components/ask/reveal";
import { Pitch } from "@/components/charts/pitch";
import { ShotMark } from "@/components/charts/shot-map";
import { barShare } from "@/lib/compare-bars";
import { HOW_IT_WORKS } from "@/lib/landing-content";
import { toPitchPoint } from "@/lib/pitch";
import { SAMPLE_SHOT_MAP } from "@/lib/sample-shots";
import { outcomeKind, shotRadius } from "@/lib/shot-map";
import { cn } from "@/lib/utils";

// The longest build-up (card 4) ends at about 2.6 s. The play class goes after
// this time, so the card rests on its finished frame. A timer is simpler than
// counting the animationend events of every part.
const PLAY_MS = 2900;

/** The place of an item in its build-up, for the delay of its keyframe. */
function step(index: number): CSSProperties {
  return { "--i": index } as CSSProperties;
}

/**
 * Plays the build-up of a card once: a mouse that enters it, a focus that
 * comes into it, or, on a touch screen, the card half in view. A play that
 * runs is not restarted, so a pointer that crosses a card twice does not make
 * it flicker. With reduced motion nothing plays.
 */
function usePlayOnce() {
  const ref = useRef<HTMLElement>(null);
  const [playing, setPlaying] = useState(false);
  const busy = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const play = () => {
    if (busy.current || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    busy.current = true;
    setPlaying(true);
    timer.current = setTimeout(() => {
      busy.current = false;
      setPlaying(false);
    }, PLAY_MS);
  };

  useEffect(() => {
    const element = ref.current;
    let observer: IntersectionObserver | undefined;
    // A touch screen has no hover: the card plays once when it comes into view.
    if (element && !matchMedia("(hover: hover) and (pointer: fine)").matches) {
      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          play();
          observer?.disconnect();
        },
        { threshold: 0.5 },
      );
      observer.observe(element);
    }
    return () => {
      observer?.disconnect();
      clearTimeout(timer.current);
    };
    // play reads only refs and a stable setter, so the effect runs once.
  }, []);

  return {
    ref,
    playing,
    onPointerEnter: (event: PointerEvent) => {
      if (event.pointerType === "mouse") play();
    },
    onFocus: play,
  };
}

type CardProps = {
  index: number;
  icon: ReactNode;
  children: ReactNode;
  onTry: (question: string) => void;
};

function Card({ index, icon, children, onTry }: CardProps) {
  const { title, text, try: tryIt } = HOW_IT_WORKS.cards[index];
  const { ref, playing, onPointerEnter, onFocus } = usePlayOnce();
  return (
    <article
      ref={ref}
      onPointerEnter={onPointerEnter}
      onFocus={onFocus}
      className={cn(
        "grid grid-rows-[1fr_auto] rounded-[18px] border bg-card p-2 transition-[border-color] duration-200 hover:border-line-strong",
        playing && styles.play,
      )}
    >
      <div className="grid grid-rows-[auto_auto_1fr] items-start gap-2 px-5.5 pt-5.5 pb-5 max-[600px]:px-4 max-[600px]:pt-4.5 max-[600px]:pb-4">
        <h3 className="flex items-center gap-2.5 font-sans text-xl leading-tight font-semibold">
          <span aria-hidden="true" className="flex text-brand">
            {icon}
          </span>
          {title}
        </h3>
        <p className="max-w-[48ch] text-[15.5px] leading-[1.55] text-muted-foreground">{text}</p>
        <button
          type="button"
          onClick={() => onTry(tryIt.question)}
          className="group mt-0.5 inline-flex min-h-target cursor-pointer items-center gap-2 self-end justify-self-start px-0.5 text-[15px] font-semibold underline decoration-line-strong underline-offset-[5px] transition-[text-decoration-color,scale] duration-150 ease-out-strong hover:decoration-foreground active:scale-[0.97]"
        >
          Try: {tryIt.label}
          <span
            aria-hidden="true"
            className="transition-transform duration-200 ease-out-strong group-hover:translate-x-[3px]"
          >
            →
          </span>
        </button>
      </div>
      {/* The live picture of the card. The text above carries the meaning. */}
      <div
        aria-hidden="true"
        className="relative grid h-80 grid-cols-[minmax(0,1fr)] place-items-center overflow-hidden rounded-xl border border-line-subtle bg-surface-sunken bg-[radial-gradient(120%_90%_at_50%_0%,rgb(255_255_255/0.03),transparent_60%)] p-6 max-[600px]:h-auto max-[600px]:min-h-[260px] max-[600px]:p-4"
      >
        {children}
      </div>
    </article>
  );
}

const MINI =
  "w-full min-w-0 rounded-[10px] border border-line-mid bg-background shadow-[0_18px_40px_rgb(0_0_0/0.35)]";

const ICON = {
  viewBox: "0 0 24 24",
  className: "size-4.5 fill-none stroke-current",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

// Card 1: an example run of the agent, in the words of its step list.
const STEPS: [string, string][] = [
  ["Read what each season holds", "catalog"],
  ["Found Thierry Henry and Bukayo Saka", "2 players"],
  ["Ran one read-only query", "1 row"],
  ["Drew the comparison", "chart"],
  ["Checked every number", "6 of 6"],
];

function AskMini() {
  return (
    <div className={cn(MINI, "grid max-w-[460px] grid-cols-[minmax(0,1fr)] gap-3 p-4")}>
      <div className="flex min-h-11 items-center gap-2.5 rounded-full border border-line-strong bg-surface-sunken py-1.5 pr-1.5 pl-4">
        <span className={cn(styles.typed, "min-w-0 flex-1 truncate text-sm")}>
          Compare Henry in 2003-04 with Saka in 2025-26 on goals per 90
        </span>
        <span
          className={cn(
            styles.ask,
            "grid min-h-8 shrink-0 place-items-center rounded-full bg-paper px-3.5 text-[13px] font-semibold text-background",
          )}
        >
          Ask
        </span>
      </div>
      <ol className="grid gap-0.5">
        {STEPS.map(([label, tag], index) => (
          <li
            key={label}
            style={step(index)}
            className={cn(
              styles.step,
              "grid min-h-7.5 grid-cols-[22px_1fr_auto] items-center gap-2.5 text-[13.5px] text-foreground-2",
            )}
          >
            <span
              style={step(index)}
              className={cn(
                styles.tick,
                "grid size-4.5 place-items-center rounded-full border border-verified-line bg-verified-bg text-[10px] font-bold text-verified",
              )}
            >
              ✓
            </span>
            {label}
            <span className="font-mono text-[11.5px] text-faint">{tag}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// Card 2: the first goal of the sample chart carries the label.
const FIRST_GOAL = SAMPLE_SHOT_MAP.shots.find((shot) => outcomeKind(shot.outcome) === "goal");

function MapMini() {
  return (
    <div className={cn(MINI, "max-w-[340px] p-3")}>
      {/* The penalty area and the space in front of it: the top of the attacking half. */}
      <div className="aspect-[84/50] overflow-hidden rounded-md">
        <Pitch view="attacking-half">
          {/* The shots land in the order of the minutes. */}
          {SAMPLE_SHOT_MAP.shots.map((shot, index) => {
            const point = toPitchPoint(shot.x, shot.y);
            return (
              <g key={`${shot.x} ${shot.y}`} transform={`translate(${point.x} ${point.y})`}>
                <g style={step(index)} className={styles.mark}>
                  <ShotMark kind={outcomeKind(shot.outcome)} r={shotRadius(shot.xg)} />
                </g>
              </g>
            );
          })}
          {FIRST_GOAL && (
            <g className={styles.label}>
              <rect
                x="50"
                y="16"
                width="27"
                height="7"
                rx="3.5"
                strokeWidth="0.3"
                className="fill-background/85 stroke-line-strong"
              />
              <text x="63.5" y="20.6" textAnchor="middle" className="fill-paper font-mono text-[3.2px]">
                Goal · xG {FIRST_GOAL.xg.toFixed(2)}
              </text>
            </g>
          )}
        </Pitch>
      </div>
    </div>
  );
}

// Card 3: league season totals from v_player_season, checked against the
// local database on 2026-11-07 (Henry 3,330 minutes, Saka 2,239 minutes, both
// full seasons). The data module of item 32c will generate these.
const COMPARE: { label: string; henry: number; saka: number; digits: number }[] = [
  { label: "Goals", henry: 30, saka: 7, digits: 0 },
  { label: "Goals per 90", henry: 0.81, saka: 0.28, digits: 2 },
  { label: "xG per 90", henry: 0.65, saka: 0.35, digits: 2 },
];
// The longer bar of a row leaves room for its value in the cell.
const BAR_ROOM = 0.78;

function CompareMini() {
  return (
    <div className={cn(MINI, "grid max-w-[380px] gap-3 p-4")}>
      <div className="grid grid-cols-[1fr_auto_1fr] items-end font-display text-[15px] leading-none font-extrabold uppercase">
        <span>
          Henry
          <small className="mt-1 block font-sans text-[11px] font-normal text-muted-foreground normal-case">
            2003-04
          </small>
        </span>
        <span />
        <span className="text-right text-brand">
          Saka
          <small className="mt-1 block font-sans text-[11px] font-normal text-muted-foreground normal-case">
            2025-26
          </small>
        </span>
      </div>
      {COMPARE.map(({ label, henry, saka, digits }, index) => {
        const max = Math.max(henry, saka);
        return (
          <div key={label} className="grid grid-cols-[1fr_76px_1fr] items-center gap-2">
            {[henry, saka].map((value, side) => (
              <div
                key={side}
                className={cn("flex items-center gap-1.5", side === 0 && "flex-row-reverse")}
                style={side === 1 ? { order: 2 } : undefined}
              >
                <span
                  style={{ ...step(index), width: `${barShare(value, max) * BAR_ROOM}%` }}
                  className={cn(
                    styles.bar,
                    "h-2.5 shrink-0 rounded-[3px]",
                    side === 0 ? "origin-right bg-foreground" : "origin-left bg-brand",
                  )}
                />
                <span
                  style={step(index)}
                  className={cn(
                    styles.value,
                    "min-w-7.5 font-display text-[13px] leading-none font-bold tabular-nums",
                    side === 0 && "text-right",
                  )}
                >
                  {value.toFixed(digits)}
                </span>
              </div>
            ))}
            <span className="order-1 text-center text-[11.5px] text-muted-foreground">{label}</span>
          </div>
        );
      })}
      <p className={cn(styles.note, "mt-0.5 text-[11.5px] leading-[1.45] text-muted-foreground")}>
        Two xG models: StatsBomb for 2003-04, Understat for 2025-26. Full league seasons.
      </p>
    </div>
  );
}

// Card 4: an example check. The three passed numbers are the checked values of
// card 3 and Saka's minutes. The removed claim is false: Saka scored 7.
const CLAIMS: { text: ReactNode; call: string; removed?: boolean }[] = [
  { text: <>Saka played <b>2,239</b> minutes</>, call: "call_02" },
  { text: <>He scored <b>0.28</b> goals per 90</>, call: "call_02" },
  { text: <>Henry scored <b>0.81</b> per 90 in 2003-04</>, call: "call_03" },
  { text: <>Saka scored <b>9</b> goals</>, call: "no source", removed: true },
];

function CheckMini() {
  return (
    <div className={cn(MINI, "grid max-w-[460px] grid-cols-[minmax(0,1fr)] gap-2 px-4 py-3.5")}>
      <div className="flex items-center justify-between gap-3 text-[12.5px] text-muted-foreground">
        <span>Verification</span>
        <b className="font-semibold text-verified">checked 4 · passed 3 · removed 1</b>
      </div>
      <ul className="grid gap-1.5">
        {CLAIMS.map(({ text, call, removed }, index) => (
          <li
            key={call + index}
            style={step(index)}
            className={cn(
              styles.claim,
              removed && styles.removed,
              "relative grid min-h-8 grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-2.5 rounded-lg bg-white/3 px-2.5 text-[13.5px]",
              removed ? "text-faint [&_b]:text-faint" : "text-foreground-2 [&_b]:text-foreground",
            )}
          >
            <span
              style={step(index)}
              className={cn(styles.claimMark, "font-bold", removed ? "text-brand" : "text-verified")}
            >
              {removed ? "✕" : "✓"}
            </span>
            <span className="[&_b]:font-bold">{text}</span>
            <code className="font-mono text-[11px] text-faint max-[1080px]:hidden">{call}</code>
            {removed && (
              <span
                className={cn(
                  styles.strike,
                  "absolute top-1/2 right-3 left-9.5 h-[1.5px] origin-left bg-brand",
                )}
              />
            )}
          </li>
        ))}
      </ul>
      <pre
        className={cn(
          styles.sql,
          "mt-0.5 overflow-hidden rounded-lg border border-line-subtle bg-surface-sunken px-3 py-2.5 font-mono text-[11.5px] leading-[1.55] text-foreground-2 max-[600px]:text-[10.5px]",
        )}
      >
        <span className="text-brand">SELECT</span> minutes, round(goals * 90.0 / minutes, 2)
        {"\n"}
        <span className="text-brand">FROM</span>   v_player_season
        {"\n"}
        <span className="text-brand">WHERE</span>  player = &apos;Bukayo Saka&apos;{" "}
        <span className="text-brand">AND</span> season = &apos;2025-26&apos;
      </pre>
    </div>
  );
}

type CapabilitiesProps = {
  // Puts a question into the hero bar. It does not ask it.
  onTry: (question: string) => void;
};

/** What the analyst can do, as four cards that each show it at work, with a question to try. */
export function Capabilities({ onTry }: CapabilitiesProps) {
  return (
    // The "How it works" link of the header goes to this id.
    <section
      id="how"
      aria-labelledby="how-title"
      className="mx-auto w-full max-w-[1200px] scroll-mt-6 pt-28 pb-30 max-[860px]:pt-18 max-[860px]:pb-22"
    >
      <Reveal className="mx-auto mb-14 grid max-w-[640px] gap-4 text-center max-[860px]:mb-10">
        <h2
          id="how-title"
          className="font-display text-[clamp(32px,3.6vw,48px)] leading-[1.04] font-semibold font-stretch-semi-expanded text-balance"
        >
          {HOW_IT_WORKS.headline[0]}
          <em className="block">{HOW_IT_WORKS.headline[1]}</em>
        </h2>
        <p className="text-[17px] text-muted-foreground">{HOW_IT_WORKS.hint}</p>
      </Reveal>
      <div className="grid auto-rows-fr grid-cols-2 gap-5 max-[860px]:auto-rows-auto max-[860px]:grid-cols-1">
        <Card
          index={0}
          onTry={onTry}
          icon={
            <svg {...ICON}>
              <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
            </svg>
          }
        >
          <AskMini />
        </Card>
        <Card
          index={1}
          onTry={onTry}
          icon={
            <svg {...ICON}>
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M12 4v16M3 12h4M17 12h4" />
            </svg>
          }
        >
          <MapMini />
        </Card>
        <Card
          index={2}
          onTry={onTry}
          icon={
            <svg {...ICON}>
              <path d="M4 7h7M4 12h11M4 17h5M20 7h-3M20 12h-1M20 17h-7" />
            </svg>
          }
        >
          <CompareMini />
        </Card>
        <Card
          index={3}
          onTry={onTry}
          icon={
            <svg {...ICON}>
              <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          }
        >
          <CheckMini />
        </Card>
      </div>
    </section>
  );
}
