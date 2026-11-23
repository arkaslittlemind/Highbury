import type { ChartSpec } from "@/lib/analyst-schema";

export type XgTimelineSpec = Extract<ChartSpec, { type: "xg_timeline" }>;
export type TimelineTeam = XgTimelineSpec["teams"][number];
export type TimelineShot = TimelineTeam["shots"][number];

export const MINUTE_TICKS = [0, 15, 30, 45, 60, 75, 90];
export const HALF_TIME = 45;

/** The last minute on the chart: 90, or the minute of a later shot. */
export function endMinute(chart: XgTimelineSpec): number {
  return Math.max(90, ...chart.teams.flatMap((team) => team.shots.map((shot) => shot.minute)));
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

/** One row of the ECharts data: the minute (a category) and each team's total after it. */
export type MinuteRow = { minute: string; t0: number; t1: number };

/** The total of a team after the shots of a minute: the spec total of its last shot by then. */
function totalAfter(team: TimelineTeam, minute: number): number {
  let total = 0;
  for (const shot of team.shots) if (shot.minute <= minute) total = shot.total;
  return total;
}

/**
 * One row for each minute from 0 to the end, for the category x axis of the area
 * chart. The values are the totals of the spec, so the chart calculates no new number.
 */
export function minuteRows(chart: XgTimelineSpec): MinuteRow[] {
  const [first, second] = chart.teams;
  return Array.from({ length: endMinute(chart) + 1 }, (_, minute) => ({
    minute: String(minute),
    t0: totalAfter(first, minute),
    t1: totalAfter(second, minute),
  }));
}

export type MarkPoint = { team: number; minute: number; total: number; isGoal: boolean };

/** The marks in markOrder order, so a keyboard index is also the index of the mark in the chart. */
export function markPoints(chart: XgTimelineSpec): MarkPoint[] {
  return markOrder(chart).map(({ team, shot }) => ({
    team,
    minute: shot.minute,
    total: shot.total,
    isGoal: shot.is_goal,
  }));
}

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * The tooltip of a shot as HTML, for the ECharts tooltip. A player name is data and
 * ECharts renders the formatter as HTML, so every line is escaped.
 */
export function tooltipHtml(mark: Mark): string {
  const [heading, ...rest] = tooltipLines(mark).map(escapeHtml);
  return [
    `<div class="font-medium text-foreground">${heading}</div>`,
    ...rest.map((line) => `<div>${line}</div>`),
  ].join("");
}

/**
 * The top and the step of the xG axis. The top is at least 1, so a match with few
 * chances does not look like a match with many.
 */
export function xgAxis(chart: XgTimelineSpec): { max: number; interval: number } {
  const highest = Math.max(1, ...chart.teams.map((team) => team.xg));
  if (highest <= 1) return { max: 1, interval: 0.25 };
  if (highest <= 3) return { max: Math.ceil(highest * 2) / 2, interval: 0.5 };
  return { max: Math.ceil(highest), interval: 1 };
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
