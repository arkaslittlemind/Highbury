"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import { ChartTitle } from "@/components/charts/chart-title";
import { Pitch } from "@/components/charts/pitch";
import { toPitchPoint } from "@/lib/pitch";
import {
  OUTCOME_KINDS,
  OUTCOME_LABELS,
  drawOrder,
  isDrawn,
  nextIndex,
  outcomeKind,
  shotLabel,
  shotRadius,
  summaryText,
  tooltipLines,
  tooltipPlace,
  type OutcomeKind,
  type Shot,
  type ShotMapSpec,
} from "@/lib/shot-map";
import { cn } from "@/lib/utils";

// A small mark is hard to hit, so each mark takes the pointer in this radius or more.
const MIN_HIT_RADIUS = 3;
// The ring of the active mark is this far outside the mark, in pitch units.
const RING_GAP = 0.8;
// The width of the tooltip: w-52.
const TOOLTIP_WIDTH = "13rem";

const STROKE = { strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" } as const;
const HOLLOW = "fill-surface-chart/60";

/** The shape of an outcome, around the origin. The outcome is the shape and not only the colour. */
function ShotMark({ kind, r }: { kind: OutcomeKind; r: number }) {
  switch (kind) {
    case "goal":
      return <circle r={r} className="fill-brand stroke-background" {...STROKE} />;
    case "saved":
      return <circle r={r} className={cn(HOLLOW, "stroke-foreground")} {...STROKE} />;
    case "blocked":
      return (
        <polygon
          points={`0,${-r} ${0.866 * r},${0.5 * r} ${-0.866 * r},${0.5 * r}`}
          strokeLinejoin="round"
          className={cn(HOLLOW, "stroke-foreground-2")}
          {...STROKE}
        />
      );
    case "off_target": {
      const arm = 0.7 * r;
      return (
        <path
          d={`M${-arm} ${-arm}L${arm} ${arm}M${arm} ${-arm}L${-arm} ${arm}`}
          strokeLinecap="round"
          className="fill-none stroke-muted-foreground"
          {...STROKE}
          strokeWidth={2}
        />
      );
    }
    case "post":
      return (
        <polygon
          points={`0,${-r} ${r},0 0,${r} ${-r},0`}
          strokeLinejoin="round"
          className={cn(HOLLOW, "stroke-foreground")}
          {...STROKE}
        />
      );
    case "other": {
      const half = 0.75 * r;
      return (
        <rect
          x={-half}
          y={-half}
          width={2 * half}
          height={2 * half}
          className={cn(HOLLOW, "stroke-muted-foreground")}
          {...STROKE}
        />
      );
    }
  }
}

function Legend({ kinds }: { kinds: OutcomeKind[] }) {
  return (
    <ul aria-label="Legend" className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-foreground-2">
      {kinds.map((kind) => (
        <li key={kind} className="flex items-center gap-2">
          <svg aria-hidden="true" width="16" height="16" viewBox="-8 -8 16 16">
            <ShotMark kind={kind} r={6} />
          </svg>
          {OUTCOME_LABELS[kind]}
        </li>
      ))}
      <li className="ml-auto flex items-center gap-2">
        <svg
          aria-hidden="true"
          width="40"
          height="16"
          viewBox="0 0 40 16"
          className="fill-none stroke-faint"
        >
          <circle cx="5" cy="8" r="2.5" />
          <circle cx="17" cy="8" r="4.5" />
          <circle cx="32" cy="8" r="7" />
        </svg>
        Low → high xG
      </li>
    </ul>
  );
}

function Tooltip({ shot }: { shot: Shot }) {
  const place = tooltipPlace(shot);
  const [heading, ...lines] = tooltipLines(shot);
  return (
    // The label of the mark has the same text, so a screen reader does not need this.
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute z-10 w-52 rounded-lg bg-foreground px-3.5 py-3 text-sm leading-snug text-background shadow-pop",
        place.side === "below" ? "mt-2" : "mb-2",
      )}
      // The place comes from the data of the shot, so it cannot be a class.
      // clamp() keeps the tooltip inside the drawing.
      style={{
        left: `clamp(0px, calc(${place.left}% - ${TOOLTIP_WIDTH} / 2), calc(100% - ${TOOLTIP_WIDTH}))`,
        ...(place.side === "below"
          ? { top: `${place.top}%` }
          : { bottom: `${100 - place.top}%` }),
      }}
    >
      <div className="font-bold">{heading}</div>
      {lines.map((line, index) => (
        <div key={index} className={cn(index > 0 && "text-tooltip-muted")}>
          {line}
        </div>
      ))}
    </div>
  );
}

/**
 * The shots of a chart on a pitch: size is xG and shape is the outcome. It
 * goes inside the figure of ChartPanel. The chart is one tab stop, and the
 * arrow keys move between the shots.
 */
export function ShotMap({ chart }: { chart: ShotMapSpec }) {
  const marks = useRef<(SVGGElement | null)[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  // The mark that Tab goes to: the last one that had the focus.
  const [tabStop, setTabStop] = useState(0);
  const [tooltipHidden, setTooltipHidden] = useState(false);

  if (chart.shots.length === 0) {
    return (
      <>
        <ChartTitle>{chart.title}</ChartTitle>
        <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
          This chart has no shots.
        </figcaption>
      </>
    );
  }

  // The marks. A shot from the own half has none, and the summary says so.
  const shots = drawOrder(chart.shots.filter(isDrawn));
  const kinds = new Set(shots.map((shot) => outcomeKind(shot.outcome)));
  const active = hovered ?? focused;
  const activeShot = active === null ? null : shots[active];

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "Escape") {
      setTooltipHidden(true);
      return;
    }
    const next = nextIndex(event.key, tabStop, shots.length);
    if (next === null) return;
    // An arrow key must not scroll the page.
    event.preventDefault();
    marks.current[next]?.focus();
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <ChartTitle>{chart.title}</ChartTitle>
        <span className="text-sm text-muted-foreground">Attacking upward · size = xG</span>
      </div>
      <div className="relative">
        <Pitch
          view="attacking-half"
          role="group"
          aria-label={`${chart.title}. ${shots.length} ${shots.length === 1 ? "shot" : "shots"} on the pitch. Use the arrow keys to move between the shots.`}
          onKeyDown={onKeyDown}
        >
          {shots.map((shot, index) => {
            const point = toPitchPoint(shot.x, shot.y);
            const r = shotRadius(shot.xg);
            return (
              <g
                key={index}
                ref={(mark) => {
                  marks.current[index] = mark;
                }}
                role="img"
                aria-label={shotLabel(shot)}
                tabIndex={index === tabStop ? 0 : -1}
                transform={`translate(${point.x} ${point.y})`}
                // The ring below is the focus indicator. Browsers draw an
                // outline on a part of an SVG in different ways.
                className="cursor-pointer outline-hidden"
                onPointerEnter={() => {
                  setHovered(index);
                  setTooltipHidden(false);
                }}
                onPointerLeave={() => setHovered(null)}
                onFocus={() => {
                  setFocused(index);
                  setTabStop(index);
                  setTooltipHidden(false);
                }}
                onBlur={() => setFocused(null)}
                // A touch screen has no hover, and a tap does not always give the focus.
                onClick={(event) => event.currentTarget.focus()}
              >
                <circle r={Math.max(r, MIN_HIT_RADIUS)} className="fill-transparent" />
                <ShotMark kind={outcomeKind(shot.outcome)} r={r} />
              </g>
            );
          })}
          {activeShot && (
            <circle
              cx={toPitchPoint(activeShot.x, activeShot.y).x}
              cy={toPitchPoint(activeShot.x, activeShot.y).y}
              r={shotRadius(activeShot.xg) + RING_GAP}
              className="pointer-events-none fill-none stroke-ring"
              {...STROKE}
              strokeWidth={3}
            />
          )}
        </Pitch>
        {activeShot && !tooltipHidden && <Tooltip shot={activeShot} />}
      </div>
      <Legend kinds={OUTCOME_KINDS.filter((kind) => kind !== "other" || kinds.has(kind))} />
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart.shots)}
      </figcaption>
    </>
  );
}
