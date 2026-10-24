"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import { ChartTitle } from "@/components/charts/chart-title";
import { PitchTooltip } from "@/components/charts/pitch-tooltip";
import {
  MARK_RADIUS,
  MATCH_TICKS,
  VIEW,
  lineColours,
  linePath,
  markLabel,
  moveMark,
  percentX,
  percentY,
  scalesOf,
  summaryText,
  tooltipLines,
  tooltipPlace,
  type MarkAt,
  type PointsPaceSpec,
} from "@/lib/points-pace";
import { cn } from "@/lib/utils";

// The marks are about 15 viewBox units apart, so a larger hit area would cover the next one.
const HIT_RADIUS = 7;
const RING_GAP = 2.5;

const STROKE = { strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" } as const;
// Each line has its own dash, so a line shows by more than its colour.
const DASHES = [undefined, "6 4", "2 4", "10 4 2 4"];

const COLOUR_STROKE = [
  "stroke-chart-1",
  "stroke-chart-2",
  "stroke-chart-3",
  "stroke-chart-4",
  "stroke-chart-5",
];

function Legend({ chart, colours }: { chart: PointsPaceSpec; colours: number[] }) {
  return (
    <ul
      aria-label="Legend"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-foreground-2"
    >
      {chart.lines.map((line, index) => (
        <li key={`${line.team} ${line.season}`} className="flex min-h-target items-center gap-2">
          <svg aria-hidden="true" width="28" height="10" viewBox="0 0 28 10">
            <line
              x1="1"
              y1="5"
              x2="27"
              y2="5"
              strokeWidth="2.5"
              strokeDasharray={DASHES[index]}
              className={COLOUR_STROKE[colours[index]]}
            />
          </svg>
          <span>
            {line.team} {line.season}{" "}
            <span className="font-semibold text-foreground">{line.points}</span> pts
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * The cumulative league points of each team and season, by matches played, with a
 * mark at each match. It goes inside the figure of ChartPanel. The chart is one tab
 * stop: Left and Right move along a line, Up and Down move between the lines.
 */
export function PointsPace({ chart }: { chart: PointsPaceSpec }) {
  const refs = useRef(new Map<string, SVGGElement>());
  const [hovered, setHovered] = useState<MarkAt | null>(null);
  const [focused, setFocused] = useState<MarkAt | null>(null);
  // The mark that Tab goes to: the last one that had the focus.
  const [tabStop, setTabStop] = useState<MarkAt>({ line: 0, match: 0 });
  const [tooltipHidden, setTooltipHidden] = useState(false);

  const scales = scalesOf(chart);
  const colours = lineColours(chart);
  const pointTicks = scales.y.ticks(5);
  const active = hovered ?? focused;
  const activeLine = active && chart.lines[active.line];
  const activeMatch = active && activeLine?.matches[active.match];
  const matchCount = chart.lines.reduce((sum, line) => sum + line.matches.length, 0);

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "Escape") {
      setTooltipHidden(true);
      return;
    }
    const next = moveMark(event.key, tabStop, chart);
    if (next === null) return;
    // An arrow key must not scroll the page.
    event.preventDefault();
    refs.current.get(`${next.line}-${next.match}`)?.focus();
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <ChartTitle>{chart.title}</ChartTitle>
        <span className="text-sm text-muted-foreground">Cumulative points by matches played</span>
      </div>
      <div>
        <div className="relative">
          <svg
            viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
            className="block h-auto w-full overflow-visible"
            role="group"
            aria-label={`${chart.title}. ${chart.lines.length} ${chart.lines.length === 1 ? "line" : "lines"}, ${matchCount} ${matchCount === 1 ? "match" : "matches"}. Use the arrow keys: left and right along a line, up and down between the lines.`}
            onKeyDown={onKeyDown}
          >
            <g aria-hidden="true" className="pointer-events-none">
              {pointTicks.map((tick) => (
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
              {/* The last line first, so that the first Arsenal line is on top where they meet. */}
              {chart.lines
                .map((line, index) => ({ line, index }))
                .reverse()
                .map(({ line, index }) => (
                  <path
                    key={index}
                    d={linePath(line, scales)}
                    fill="none"
                    strokeWidth={2.5}
                    strokeLinejoin="round"
                    strokeDasharray={DASHES[index]}
                    vectorEffect="non-scaling-stroke"
                    className={COLOUR_STROKE[colours[index]]}
                  />
                ))}
            </g>
            {chart.lines.map((line, lineIndex) =>
              line.matches.map((match, matchIndex) => {
                const at = { line: lineIndex, match: matchIndex };
                const key = `${lineIndex}-${matchIndex}`;
                const isTabStop = tabStop.line === lineIndex && tabStop.match === matchIndex;
                return (
                  <g
                    key={key}
                    ref={(element) => {
                      if (element) refs.current.set(key, element);
                      else refs.current.delete(key);
                    }}
                    role="img"
                    aria-label={markLabel(line, match)}
                    tabIndex={isTabStop ? 0 : -1}
                    transform={`translate(${scales.x(match.matchday)} ${scales.y(match.total)})`}
                    // The ring below is the focus indicator. Browsers draw an
                    // outline on a part of an SVG in different ways.
                    className="cursor-pointer outline-hidden"
                    onPointerEnter={() => {
                      setHovered(at);
                      setTooltipHidden(false);
                    }}
                    onPointerLeave={() => setHovered(null)}
                    onFocus={() => {
                      setFocused(at);
                      setTabStop(at);
                      setTooltipHidden(false);
                    }}
                    onBlur={() => setFocused(null)}
                    // A touch screen has no hover, and a tap does not always give the focus.
                    onClick={(event) => event.currentTarget.focus()}
                  >
                    <circle r={HIT_RADIUS} className="fill-transparent" />
                    <circle
                      r={MARK_RADIUS}
                      className={cn("fill-surface-chart", COLOUR_STROKE[colours[lineIndex]])}
                      {...STROKE}
                    />
                  </g>
                );
              }),
            )}
            {activeMatch && (
              <circle
                cx={scales.x(activeMatch.matchday)}
                cy={scales.y(activeMatch.total)}
                r={MARK_RADIUS + RING_GAP}
                className="pointer-events-none fill-none stroke-ring"
                {...STROKE}
                strokeWidth={3}
              />
            )}
          </svg>
          {/* The labels are HTML, so they keep their size when the drawing is narrow. */}
          {pointTicks.map((tick) => (
            <span
              key={tick}
              aria-hidden="true"
              className="pointer-events-none absolute left-0 -translate-y-full pb-0.5 text-xs text-muted-foreground tabular-nums"
              // The place comes from the data of the chart, so it cannot be a class.
              style={{ top: `${percentY(tick, scales)}%` }}
            >
              {tick === 0 ? "" : tick}
            </span>
          ))}
          {activeLine && activeMatch && !tooltipHidden && (
            <PitchTooltip
              place={tooltipPlace(activeMatch, scales)}
              lines={tooltipLines(activeLine, activeMatch)}
            />
          )}
        </div>
        <div aria-hidden="true" className="relative mt-1.5 h-4 text-xs text-muted-foreground">
          {MATCH_TICKS.map((matchday) => (
            <span
              key={matchday}
              className={cn("absolute tabular-nums", matchday > 0 && "-translate-x-1/2")}
              style={{ left: `${percentX(matchday, scales)}%` }}
            >
              {matchday}
            </span>
          ))}
        </div>
      </div>
      <Legend chart={chart} colours={colours} />
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart)}
      </figcaption>
    </>
  );
}
