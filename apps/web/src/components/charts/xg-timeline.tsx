"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import { ChartTitle } from "@/components/charts/chart-title";
import { PitchTooltip } from "@/components/charts/pitch-tooltip";
import { nextIndex } from "@/lib/shot-map";
import { cn } from "@/lib/utils";
import {
  GOAL_RADIUS,
  HALF_TIME,
  MINUTE_TICKS,
  SHOT_RADIUS,
  VIEW,
  endMinute,
  linePath,
  markOrder,
  percentX,
  percentY,
  scalesOf,
  shotLabel,
  stepPoints,
  summaryText,
  tooltipLines,
  tooltipPlace,
  type XgTimelineSpec,
} from "@/lib/xg-timeline";

// A small mark is hard to hit, so each mark takes the pointer in this radius or more.
const MIN_HIT_RADIUS = 10;
// The ring of the active mark is this far outside the mark, in viewBox units.
const RING_GAP = 2.5;

const STROKE = { strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" } as const;
// The opponent's line is dashed, so the team shows by more than its colour.
const DASH = "6 4";

// Arsenal (team 0) is the brand colour and the opponent is the text colour.
const TEAM_STROKE = ["stroke-brand", "stroke-foreground"];
const TEAM_FILL = ["fill-brand", "fill-foreground"];

/** The mark of a shot, around the origin. A goal is larger and filled, so it shows by shape. */
function TimelineMark({ team, isGoal }: { team: number; isGoal: boolean }) {
  return isGoal ? (
    <circle r={GOAL_RADIUS} className={cn(TEAM_FILL[team], "stroke-background")} {...STROKE} />
  ) : (
    <circle r={SHOT_RADIUS} className={cn("fill-surface-chart", TEAM_STROKE[team])} {...STROKE} />
  );
}

function Legend({ chart }: { chart: XgTimelineSpec }) {
  return (
    <ul
      aria-label="Legend"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-foreground-2"
    >
      {chart.teams.map((team, index) => (
        <li key={team.team} className="flex min-h-target items-center gap-2">
          <svg aria-hidden="true" width="28" height="10" viewBox="0 0 28 10">
            <line
              x1="1"
              y1="5"
              x2="27"
              y2="5"
              strokeWidth="2.5"
              strokeDasharray={index === 1 ? DASH : undefined}
              className={TEAM_STROKE[index]}
            />
          </svg>
          <span>
            {team.team} <span className="font-semibold text-foreground">{team.xg.toFixed(2)}</span>{" "}
            xG
          </span>
        </li>
      ))}
      <li className="flex min-h-target items-center gap-2">
        <svg aria-hidden="true" width="16" height="16" viewBox="-8 -8 16 16">
          <circle r="6" className="fill-foreground stroke-background" {...STROKE} />
        </svg>
        Goal
      </li>
      <li className="flex min-h-target items-center gap-2">
        <svg aria-hidden="true" width="16" height="16" viewBox="-8 -8 16 16">
          <circle r="3.5" className="fill-surface-chart stroke-foreground" {...STROKE} />
        </svg>
        Shot
      </li>
    </ul>
  );
}

/**
 * The cumulative xG of both teams in one match, as step lines by minute, with a
 * mark at each shot. It goes inside the figure of ChartPanel. The chart is one
 * tab stop, and the arrow keys move between the shots in minute order.
 */
export function XgTimeline({ chart }: { chart: XgTimelineSpec }) {
  const refs = useRef<(SVGGElement | null)[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  // The mark that Tab goes to: the last one that had the focus.
  const [tabStop, setTabStop] = useState(0);
  const [tooltipHidden, setTooltipHidden] = useState(false);

  const marks = markOrder(chart);
  if (marks.length === 0) {
    return (
      <>
        <ChartTitle>{chart.title}</ChartTitle>
        <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
          This chart has no shots.
        </figcaption>
      </>
    );
  }

  const end = endMinute(chart);
  const scales = scalesOf(chart);
  const xgTicks = scales.y.ticks(4);
  const active = hovered ?? focused;
  const activeMark = active === null ? null : marks[active];

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "Escape") {
      setTooltipHidden(true);
      return;
    }
    const next = nextIndex(event.key, tabStop, marks.length);
    if (next === null) return;
    // An arrow key must not scroll the page.
    event.preventDefault();
    refs.current[next]?.focus();
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <ChartTitle>{chart.title}</ChartTitle>
        <span className="text-sm text-muted-foreground">Cumulative xG by minute</span>
      </div>
      <div>
        <div className="relative">
          <svg
            viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
            className="block h-auto w-full overflow-visible"
            role="group"
            aria-label={`${chart.title}. ${marks.length} ${marks.length === 1 ? "shot" : "shots"}. Use the arrow keys to move between the shots.`}
            onKeyDown={onKeyDown}
          >
            <g aria-hidden="true" className="pointer-events-none">
              {xgTicks.map((tick) => (
                <line
                  key={tick}
                  x1={0}
                  x2={VIEW.width}
                  y1={scales.y(tick)}
                  y2={scales.y(tick)}
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                  className={tick === 0 ? "stroke-line-mid" : "stroke-line-subtle"}
                />
              ))}
              <line
                x1={scales.x(HALF_TIME)}
                x2={scales.x(HALF_TIME)}
                y1={scales.y(scales.y.domain()[1])}
                y2={scales.y(0)}
                strokeWidth={1}
                strokeDasharray="2 4"
                vectorEffect="non-scaling-stroke"
                className="stroke-line-mid"
              />
              {/* The opponent first, so that Arsenal's line is on top where they meet. */}
              {[1, 0].map((index) => (
                <path
                  key={index}
                  d={linePath(stepPoints(chart.teams[index], end), scales)}
                  fill="none"
                  strokeWidth={2.5}
                  strokeLinejoin="round"
                  strokeDasharray={index === 1 ? DASH : undefined}
                  vectorEffect="non-scaling-stroke"
                  className={TEAM_STROKE[index]}
                />
              ))}
            </g>
            {marks.map((mark, index) => (
              <g
                key={index}
                ref={(element) => {
                  refs.current[index] = element;
                }}
                role="img"
                aria-label={shotLabel(mark)}
                tabIndex={index === tabStop ? 0 : -1}
                transform={`translate(${scales.x(mark.shot.minute)} ${scales.y(mark.shot.total)})`}
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
                <circle r={MIN_HIT_RADIUS} className="fill-transparent" />
                <TimelineMark team={mark.team} isGoal={mark.shot.is_goal} />
              </g>
            ))}
            {activeMark && (
              <circle
                cx={scales.x(activeMark.shot.minute)}
                cy={scales.y(activeMark.shot.total)}
                r={(activeMark.shot.is_goal ? GOAL_RADIUS : SHOT_RADIUS) + RING_GAP}
                className="pointer-events-none fill-none stroke-ring"
                {...STROKE}
                strokeWidth={3}
              />
            )}
          </svg>
          {/* The labels are HTML, so they keep their size when the drawing is narrow. */}
          {xgTicks.map((tick) => (
            <span
              key={tick}
              aria-hidden="true"
              className="pointer-events-none absolute left-0 -translate-y-full pb-0.5 text-xs text-muted-foreground tabular-nums"
              // The place comes from the data of the chart, so it cannot be a class.
              style={{ top: `${percentY(tick, scales)}%` }}
            >
              {tick === 0 ? "" : tick.toFixed(1)}
            </span>
          ))}
          {activeMark && !tooltipHidden && (
            <PitchTooltip place={tooltipPlace(activeMark, scales)} lines={tooltipLines(activeMark)} />
          )}
        </div>
        <div aria-hidden="true" className="relative mt-1.5 h-4 text-xs text-muted-foreground">
          {MINUTE_TICKS.filter((minute) => minute <= end).map((minute) => (
            <span
              key={minute}
              className={cn("absolute tabular-nums", minute > 0 && "-translate-x-1/2")}
              style={{ left: `${percentX(minute, scales)}%` }}
            >
              {minute === HALF_TIME ? "HT" : `${minute}'`}
            </span>
          ))}
        </div>
      </div>
      <Legend chart={chart} />
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart)}
      </figcaption>
    </>
  );
}
