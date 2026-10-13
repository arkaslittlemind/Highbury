import { scaleSqrt } from "d3-scale";

import type { ChartSpec } from "@/lib/analyst-schema";
import { PITCH_LENGTH, isInPenaltyArea, toPitchPoint, viewBoxOf } from "@/lib/pitch";

export type ShotMapSpec = Extract<ChartSpec, { type: "shot_map" }>;
export type Shot = ShotMapSpec["shots"][number];

// The order of the legend and of the summary.
export const OUTCOME_KINDS = ["goal", "saved", "blocked", "off_target", "post", "other"] as const;
export type OutcomeKind = (typeof OUTCOME_KINDS)[number];

export const OUTCOME_LABELS: Record<OutcomeKind, string> = {
  goal: "Goal",
  saved: "Saved",
  blocked: "Blocked",
  off_target: "Off target",
  post: "Post",
  other: "Other",
};

// The five values that the loaders store. The service does not restrict the
// text, so a value that is not here is "other".
const STORED_OUTCOMES = new Map<string, OutcomeKind>([
  ["goal", "goal"],
  ["saved", "saved"],
  ["blocked", "blocked"],
  ["off target", "off_target"],
  ["post", "post"],
]);

export function outcomeKind(outcome: string): OutcomeKind {
  return STORED_OUTCOMES.get(outcome) ?? "other";
}

function outcomeText(shot: Shot): string {
  const kind = outcomeKind(shot.outcome);
  return kind === "other" ? shot.outcome : OUTCOME_LABELS[kind];
}

// A square-root scale, so that the area of a mark grows with xG. The range
// starts above zero, so that a shot with an xG of 0 is visible.
const radius = scaleSqrt().domain([0, 1]).range([1, 5]).clamp(true);

/** The radius of the mark of a shot, in pitch units. */
export function shotRadius(xg: number): number {
  return radius(xg);
}

/**
 * True for a shot that the map draws. The map shows the attacking half only:
 * one shot from the own half would put a full season on the full pitch, where
 * the marks are too small to read. The summary names the shots that are not shown.
 */
export function isDrawn(shot: Shot): boolean {
  return shot.x >= PITCH_LENGTH / 2;
}

/**
 * The shots from the highest xG to the lowest. Large marks are drawn first, so
 * a small mark is not hidden below a large one. The keyboard uses this order too.
 */
export function drawOrder(shots: Shot[]): Shot[] {
  return [...shots].sort((first, second) => second.xg - first.xg);
}

/** The shots that the filter of the legend does not hide. */
export function withoutKinds(shots: Shot[], hidden: ReadonlySet<OutcomeKind>): Shot[] {
  return shots.filter((shot) => !hidden.has(outcomeKind(shot.outcome)));
}

function countText(kind: OutcomeKind, count: number): string {
  switch (kind) {
    case "goal":
      return `${count} ${count === 1 ? "goal" : "goals"}`;
    case "off_target":
      return `${count} off target`;
    case "post":
      return `${count} off the post`;
    default:
      return `${count} ${kind}`;
  }
}

/**
 * The chart in words. It holds counts only: a sum of xG made here can differ
 * in the last digit from the checked number in the answer.
 */
export function summaryText(shots: Shot[]): string {
  const counts = new Map<OutcomeKind, number>();
  for (const shot of shots) {
    const kind = outcomeKind(shot.outcome);
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }
  const outcomes = OUTCOME_KINDS.filter((kind) => counts.has(kind))
    .map((kind) => countText(kind, counts.get(kind) ?? 0))
    .join(", ");
  const inArea = shots.filter((shot) => isInPenaltyArea(shot.x, shot.y)).length;
  const total = `${shots.length} ${shots.length === 1 ? "shot" : "shots"}`;
  const summary = `${total}: ${outcomes}. ${inArea} from inside the penalty area.`;
  const hidden = shots.filter((shot) => !isDrawn(shot)).length;
  if (hidden === 0) return summary;
  return `${summary} ${hidden === 1 ? "1 shot from the own half is" : `${hidden} shots from the own half are`} not shown.`;
}

function xgText(shot: Shot): string {
  return `xG ${shot.xg.toFixed(2)}`;
}

function matchDetails(shot: Shot): string[] {
  return [shot.player, shot.match_date].filter((detail): detail is string => Boolean(detail));
}

/** The accessible name of the mark of a shot. */
export function shotLabel(shot: Shot): string {
  return [
    outcomeText(shot),
    xgText(shot),
    `minute ${shot.minute}`,
    `against ${shot.opponent}`,
    ...matchDetails(shot),
  ].join(", ");
}

/** The lines of the tooltip of a shot. The first one is the heading. */
export function tooltipLines(shot: Shot): string[] {
  const lines = [
    `${outcomeText(shot)} · ${xgText(shot)}`,
    `Minute ${shot.minute} · v ${shot.opponent}`,
  ];
  const details = matchDetails(shot);
  if (details.length > 0) lines.push(details.join(" · "));
  return lines;
}

export type TooltipPlace = {
  // The centre of the mark, as a percentage of the width of the drawing.
  left: number;
  // The edge of the mark that the tooltip touches, as a percentage of the height.
  top: number;
  side: "above" | "below";
};

/** Where the tooltip of a shot goes. It is on the side of the mark that has more room. */
export function tooltipPlace(shot: Shot): TooltipPlace {
  const box = viewBoxOf("attacking-half");
  const point = toPitchPoint(shot.x, shot.y);
  const side = point.y - box.minY < box.height / 2 ? "below" : "above";
  const reach = shotRadius(shot.xg);
  const edge = side === "below" ? point.y + reach : point.y - reach;
  return {
    left: ((point.x - box.minX) / box.width) * 100,
    top: ((edge - box.minY) / box.height) * 100,
    side,
  };
}

/** The shot that a key moves to, or null for a key that does not move. The list does not wrap. */
export function nextIndex(key: string, index: number, count: number): number | null {
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return Math.min(index + 1, count - 1);
    case "ArrowLeft":
    case "ArrowUp":
      return Math.max(index - 1, 0);
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}
