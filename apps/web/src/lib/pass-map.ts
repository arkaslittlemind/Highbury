import type { ChartSpec } from "@/lib/analyst-schema";
import { toPitchPoint, tooltipPlaceAt, type TooltipPlace } from "@/lib/pitch";

export type PassMapSpec = Extract<ChartSpec, { type: "pass_map" }>;
export type Pass = PassMapSpec["passes"][number];

// The order of the legend.
export const PASS_KINDS = ["completed", "incomplete"] as const;
export type PassKind = (typeof PASS_KINDS)[number];

export const PASS_LABELS: Record<PassKind, string> = {
  completed: "Completed",
  incomplete: "Incomplete",
};

/** A pass with no outcome is completed, as in v_passes. */
export function passKind(pass: Pass): PassKind {
  return pass.outcome === null ? "completed" : "incomplete";
}

/** The length of a pass in yards: the pitch is 120 x 80 yards. */
export function passLength(pass: Pass): number {
  return Math.hypot(pass.end_x - pass.x, pass.end_y - pass.y);
}

/** The passes that the filter of the legend does not hide. */
export function withoutKinds(passes: Pass[], hidden: ReadonlySet<PassKind>): Pass[] {
  return passes.filter((pass) => !hidden.has(passKind(pass)));
}

function lengthText(pass: Pass): string {
  return `${Math.round(passLength(pass))} yards`;
}

/**
 * The chart in words, for one pass or more. The percentage is a whole number,
 * so it can differ in the last digit from the checked number in the answer.
 */
export function summaryText(passes: Pass[]): string {
  const completed = passes.filter((pass) => passKind(pass) === "completed").length;
  const share = Math.round((completed / passes.length) * 100);
  const total = `${passes.length} ${passes.length === 1 ? "pass" : "passes"}`;
  const longest = Math.max(...passes.map(passLength));
  return `${total}, ${completed} completed (${share}%). Longest: ${Math.round(longest)} yards.`;
}

/** What happened to the pass: who got it, or why it failed. */
function resultText(pass: Pass): string {
  // StatsBomb's general failure is "incomplete", which adds nothing to the kind.
  if (pass.outcome === "incomplete") return "Incomplete";
  if (pass.outcome !== null) return `Incomplete: ${pass.outcome}`;
  return pass.recipient ? `To ${pass.recipient}` : "Completed";
}

/** The accessible name of the arrow of a pass. */
export function passLabel(pass: Pass): string {
  return [
    resultText(pass),
    lengthText(pass),
    `minute ${pass.minute}`,
    `against ${pass.opponent}`,
    ...(pass.match_date ? [pass.match_date] : []),
  ].join(", ");
}

/** The lines of the tooltip of a pass. The first one is the heading. */
export function tooltipLines(pass: Pass): string[] {
  const lines = [
    `${resultText(pass)} · ${lengthText(pass)}`,
    `Minute ${pass.minute} · v ${pass.opponent}`,
  ];
  if (pass.match_date) lines.push(pass.match_date);
  return lines;
}

/** Where the tooltip of a pass goes: at the end of its arrow, on the side with more room. */
export function tooltipPlace(pass: Pass): TooltipPlace {
  return tooltipPlaceAt(toPitchPoint(pass.end_x, pass.end_y), 1, "full");
}
