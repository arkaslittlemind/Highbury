import { scaleLinear } from "d3-scale";

import type { ChartSpec } from "@/lib/analyst-schema";
import type { TooltipPlace } from "@/lib/pitch";

export type XgTimelineSpec = Extract<ChartSpec, { type: "xg_timeline" }>;
export type TimelineTeam = XgTimelineSpec["teams"][number];
export type TimelineShot = TimelineTeam["shots"][number];

/** The size of the drawing, in the units of its viewBox. */
export const VIEW = { width: 600, height: 320 };
// The marks need room at the edges, so the lines start and stop inside the drawing.
const INSET = { x: 10, top: 14, bottom: 8 };

export const MINUTE_TICKS = [0, 15, 30, 45, 60, 75, 90];
export const HALF_TIME = 45;

// The radius of the mark of a shot and of a goal, in the units of the viewBox.
export const SHOT_RADIUS = 3.5;
export const GOAL_RADIUS = 6.5;

/** The last minute on the chart: 90, or the minute of a later shot. */
export function endMinute(chart: XgTimelineSpec): number {
  return Math.max(90, ...chart.teams.flatMap((team) => team.shots.map((shot) => shot.minute)));
}

/**
 * The scales from minutes and xG to the viewBox. The xG axis goes to at least 1,
 * so a match with few chances does not look like a match with many.
 */
export function scalesOf(chart: XgTimelineSpec) {
  const x = scaleLinear()
    .domain([0, endMinute(chart)])
    .range([INSET.x, VIEW.width - INSET.x]);
  const highest = Math.max(1, ...chart.teams.map((team) => team.xg));
  const y = scaleLinear()
    .domain([0, highest])
    .nice(4)
    .range([VIEW.height - INSET.bottom, INSET.top]);
  return { x, y };
}

export type Scales = ReturnType<typeof scalesOf>;

export type StepPoint = { minute: number; xg: number };

/**
 * The corners of the step line of a team: flat until a shot, then up by its xG.
 * The heights are the totals of the spec, so the chart calculates no new number.
 */
export function stepPoints(team: TimelineTeam, end: number): StepPoint[] {
  const points = [{ minute: 0, xg: 0 }];
  let total = 0;
  for (const shot of team.shots) {
    points.push({ minute: shot.minute, xg: total });
    total = shot.total;
    points.push({ minute: shot.minute, xg: total });
  }
  points.push({ minute: end, xg: total });
  return points;
}

/** The SVG path of the corners. */
export function linePath(points: StepPoint[], scales: Scales): string {
  return points
    .map(({ minute, xg }, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command}${scales.x(minute)} ${scales.y(xg)}`;
    })
    .join("");
}

/** A place on the chart as a percentage of the drawing, for the labels and the tooltip. */
export function percentX(minute: number, scales: Scales): number {
  return (scales.x(minute) / VIEW.width) * 100;
}

export function percentY(xg: number, scales: Scales): number {
  return (scales.y(xg) / VIEW.height) * 100;
}

export type Mark = { team: number; name: string; shot: TimelineShot };

/**
 * Every shot of both teams in minute order. On a tie Arsenal (team 0) comes
 * first, and the shots of one team keep their order. The keyboard uses this order.
 */
export function markOrder(chart: XgTimelineSpec): Mark[] {
  const marks = chart.teams.flatMap((team, index) =>
    team.shots.map((shot) => ({ team: index, name: team.team, shot })),
  );
  // sort() is stable, so the order inside one team and minute is kept.
  return marks.sort(
    (first, second) => first.shot.minute - second.shot.minute || first.team - second.team,
  );
}

function xgText(value: number): string {
  return value.toFixed(2);
}

function kindText(shot: TimelineShot): string {
  return shot.is_goal ? "Goal" : "Shot";
}

/** The accessible name of the mark of a shot. */
export function shotLabel(mark: Mark): string {
  const { shot } = mark;
  return [
    kindText(shot),
    ...(shot.player ? [shot.player] : []),
    mark.name,
    `minute ${shot.minute}`,
    `xG ${xgText(shot.xg)}`,
    `${mark.name} total ${xgText(shot.total)} xG`,
  ].join(", ");
}

/** The lines of the tooltip of a shot. The first one is the heading. */
export function tooltipLines(mark: Mark): string[] {
  const { shot } = mark;
  return [
    `${kindText(shot)} · xG ${xgText(shot.xg)}`,
    [`Minute ${shot.minute}`, shot.player ?? mark.name].join(" · "),
    `${mark.name} total: ${xgText(shot.total)} xG`,
  ];
}

/** Where the tooltip of a shot goes: on the side of the mark that has more room. */
export function tooltipPlace(mark: Mark, scales: Scales): TooltipPlace {
  const x = scales.x(mark.shot.minute);
  const y = scales.y(mark.shot.total);
  const reach = mark.shot.is_goal ? GOAL_RADIUS : SHOT_RADIUS;
  const side = y < VIEW.height / 2 ? "below" : "above";
  const edge = side === "below" ? y + reach : y - reach;
  return { left: (x / VIEW.width) * 100, top: (edge / VIEW.height) * 100, side };
}

function teamSentence(team: TimelineTeam): string {
  const count = team.shots.length;
  const shots = `${count} ${count === 1 ? "shot" : "shots"}`;
  const goals = team.shots.filter((shot) => shot.is_goal);
  const scorers = goals
    .map((shot) => (shot.player ? `${shot.player} ${shot.minute}'` : `${shot.minute}'`))
    .join(", ");
  const goalText =
    goals.length === 0
      ? "no goal"
      : `${goals.length} ${goals.length === 1 ? "goal" : "goals"} (${scorers})`;
  return `${team.team}: ${xgText(team.xg)} xG from ${shots}, ${goalText}.`;
}

/** The chart in words. The xG numbers are the totals of the spec. */
export function summaryText(chart: XgTimelineSpec): string {
  return [
    ...chart.teams.map(teamSentence),
    "Own goals are not shots, so they have no mark.",
  ].join(" ");
}
