import { scaleLinear } from "d3-scale";

import type { ChartSpec } from "@/lib/analyst-schema";
import type { TooltipPlace } from "@/lib/pitch";

export type PointsPaceSpec = Extract<ChartSpec, { type: "points_pace" }>;
export type PaceLine = PointsPaceSpec["lines"][number];
export type PaceMatch = PaceLine["matches"][number];

/** The size of the drawing, in the units of its viewBox. */
export const VIEW = { width: 600, height: 320 };
// The marks need room at the edges, so the lines start and stop inside the drawing.
const INSET = { x: 10, top: 14, bottom: 8 };

// Fixed at a whole season, so the pace of a short line compares with a full one.
export const SEASON_MATCHES = 38;
export const MATCH_TICKS = [0, 10, 20, 30, 38];
export const MARK_RADIUS = 3;

const ARSENAL = "Arsenal";
// The chart colours of globals.css: 2003-04 is off-white and 2025-26 is red.
const SEASON_COLOUR: Record<string, number> = { "2003-04": 0, "2025-26": 1 };
const FIRST_OTHER_COLOUR = 2;

/** The scales from matches played and points to the viewBox. */
export function scalesOf(chart: PointsPaceSpec) {
  const x = scaleLinear()
    .domain([0, SEASON_MATCHES])
    .range([INSET.x, VIEW.width - INSET.x]);
  const highest = Math.max(1, ...chart.lines.map((line) => line.points));
  const y = scaleLinear()
    .domain([0, highest])
    .nice(5)
    .range([VIEW.height - INSET.bottom, INSET.top]);
  return { x, y };
}

export type Scales = ReturnType<typeof scalesOf>;

/** The SVG path of a line: from 0 points before the first match through each total. */
export function linePath(line: PaceLine, scales: Scales): string {
  const corners = [{ matchday: 0, total: 0 }, ...line.matches];
  return corners
    .map(({ matchday, total }, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command}${scales.x(matchday)} ${scales.y(total)}`;
    })
    .join("");
}

/**
 * The chart colour of each line. An Arsenal line takes the colour of its season,
 * as the other charts do; the other lines take the next colours in order.
 */
export function lineColours(chart: PointsPaceSpec): number[] {
  let next = FIRST_OTHER_COLOUR;
  return chart.lines.map((line) =>
    line.team === ARSENAL && line.season in SEASON_COLOUR ? SEASON_COLOUR[line.season] : next++,
  );
}

/** The place of a mark: a line, and a match of that line. */
export type MarkAt = { line: number; match: number };

/**
 * The mark that a key moves to, or null for a key that does not move. Left and
 * Right go along a line. Up and Down go to the same matchday of the line before
 * or after, or to its last match when that line is shorter.
 */
export function moveMark(key: string, at: MarkAt, chart: PointsPaceSpec): MarkAt | null {
  const last = chart.lines[at.line].matches.length - 1;
  const toLine = (line: number) => ({
    line,
    match: Math.min(at.match, chart.lines[line].matches.length - 1),
  });
  switch (key) {
    case "ArrowRight":
      return { ...at, match: Math.min(at.match + 1, last) };
    case "ArrowLeft":
      return { ...at, match: Math.max(at.match - 1, 0) };
    case "Home":
      return { ...at, match: 0 };
    case "End":
      return { ...at, match: last };
    case "ArrowDown":
      return toLine(Math.min(at.line + 1, chart.lines.length - 1));
    case "ArrowUp":
      return toLine(Math.max(at.line - 1, 0));
    default:
      return null;
  }
}

const RESULT = { 3: "W", 1: "D", 0: "L" } as const;

function lineName(line: PaceLine): string {
  return `${line.team} ${line.season}`;
}

function pointsText(points: number): string {
  return `${points} ${points === 1 ? "point" : "points"}`;
}

function resultText(match: PaceMatch): string {
  return `${RESULT[match.points]} ${match.goals_for}-${match.goals_against} v ${match.opponent}`;
}

/** The accessible name of the mark of a match. */
export function markLabel(line: PaceLine, match: PaceMatch): string {
  return [
    lineName(line),
    `match ${match.matchday}`,
    match.match_date,
    resultText(match),
    `${pointsText(match.total)} in total`,
  ].join(", ");
}

/** The lines of the tooltip of a match. The first one is the heading. */
export function tooltipLines(line: PaceLine, match: PaceMatch): string[] {
  return [
    `${lineName(line)} · Match ${match.matchday}`,
    `${resultText(match)} · ${match.match_date}`,
    `Total: ${pointsText(match.total)}`,
  ];
}

/** Where the tooltip of a match goes: on the side of the mark that has more room. */
export function tooltipPlace(match: PaceMatch, scales: Scales): TooltipPlace {
  const x = scales.x(match.matchday);
  const y = scales.y(match.total);
  const side = y < VIEW.height / 2 ? "below" : "above";
  const edge = side === "below" ? y + MARK_RADIUS : y - MARK_RADIUS;
  return { left: (x / VIEW.width) * 100, top: (edge / VIEW.height) * 100, side };
}

/** A place on the chart as a percentage of the drawing, for the labels. */
export function percentX(matchday: number, scales: Scales): number {
  return (scales.x(matchday) / VIEW.width) * 100;
}

export function percentY(points: number, scales: Scales): number {
  return (scales.y(points) / VIEW.height) * 100;
}

function lineSentence(line: PaceLine): string {
  const count = (points: number) => line.matches.filter((match) => match.points === points).length;
  const played = line.matches.length;
  const matches = `${played} ${played === 1 ? "match" : "matches"}`;
  return (
    `${lineName(line)}: ${pointsText(line.points)} from ${matches}` +
    ` (${count(3)} won, ${count(1)} drawn, ${count(0)} lost).`
  );
}

/** The chart in words. The points are the totals of the spec. */
export function summaryText(chart: PointsPaceSpec): string {
  return chart.lines.map(lineSentence).join(" ");
}
