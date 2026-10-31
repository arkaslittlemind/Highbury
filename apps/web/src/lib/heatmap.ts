import type { ChartSpec } from "@/lib/analyst-schema";
import { toPitchPoint, tooltipPlaceAt, type TooltipPlace } from "@/lib/pitch";

export type HeatmapSpec = Extract<ChartSpec, { type: "heatmap" }>;
export type Zone = HeatmapSpec["zones"][number];

// The side of a zone, in pitch units.
export const ZONE_SIZE = 10;
// The final third starts 80 from the goal line of the player's own team.
const FINAL_THIRD_ZONE = 8;
// The faintest zone must still show on the pitch, and the busiest must not hide its lines.
export const MIN_OPACITY = 0.15;
export const MAX_OPACITY = 0.85;

const numbers = new Intl.NumberFormat("en-GB");

function touchesText(count: number): string {
  return `${numbers.format(count)} ${count === 1 ? "touch" : "touches"}`;
}

/** The rect of a zone on the drawing, where the attack goes up the screen. */
export function zoneRect(zone: Zone): {
  x: number;
  y: number;
  width: number;
  height: number;
} {
  // The far corner along the length is the top left of the rect on the drawing.
  const corner = toPitchPoint((zone.zone_x + 1) * ZONE_SIZE, zone.zone_y * ZONE_SIZE);
  return { x: corner.x, y: corner.y, width: ZONE_SIZE, height: ZONE_SIZE };
}

/** The opacity of a zone: its touches against the busiest zone of the chart. */
export function zoneOpacity(touches: number, most: number): number {
  return MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * (touches / most);
}

/**
 * The shades of the scale key, from the fewest touches in one zone to the most. Each
 * end is the shade of a drawn zone, because the key uses the opacity of the zones.
 */
export function keyOpacities(fewest: number, most: number, steps: number): number[] {
  return Array.from({ length: steps }, (_, step) =>
    zoneOpacity(fewest + ((most - fewest) * step) / (steps - 1), most),
  );
}

/** The share of all touches, as a whole %, with "<1%" for a small share that is not none. */
export function shareText(touches: number, total: number): string {
  const share = Math.round((touches / total) * 100);
  return share === 0 && touches > 0 ? "<1%" : `${share}%`;
}

/** The part of the pitch that a zone is in, from the view of the attacking player. */
export function zonePlace(zone: Zone): string {
  const third =
    zone.zone_x >= FINAL_THIRD_ZONE
      ? "Final third"
      : zone.zone_x >= FINAL_THIRD_ZONE / 2
        ? "Middle third"
        : "Defensive third";
  // y = 0 is the left touchline: 0 to 30 is the left, 30 to 50 the centre, 50 to 80 the right.
  const side = zone.zone_y <= 2 ? "left" : zone.zone_y <= 4 ? "centre" : "right";
  return `${third}, ${side}`;
}

/** The zone with the most touches. On a tie, the first one in the rows. */
export function busiestZone(zones: Zone[]): Zone {
  return zones.reduce((best, zone) => (zone.touches > best.touches ? zone : best));
}

/**
 * The chart in words. The percentage is a whole number, so it can differ in the
 * last digit from a checked number in the answer.
 */
export function summaryText(chart: HeatmapSpec): string {
  const final = chart.zones
    .filter((zone) => zone.zone_x >= FINAL_THIRD_ZONE)
    .reduce((sum, zone) => sum + zone.touches, 0);
  const busiest = busiestZone(chart.zones);
  const finalShare = shareText(final, chart.total).replace("<1%", "Under 1%");
  return (
    `${touchesText(chart.total)}. ${finalShare} in the final third.` +
    ` Busiest zone: ${touchesText(busiest.touches)} (${zonePlace(busiest).toLowerCase()}).`
  );
}

/** The accessible name of a zone. */
export function zoneLabel(zone: Zone, total: number): string {
  return `${touchesText(zone.touches)}, ${shareText(zone.touches, total)} of all, ${zonePlace(zone).toLowerCase()}`;
}

/** The lines of the tooltip of a zone. The first one is the heading. */
export function tooltipLines(zone: Zone, total: number): string[] {
  return [
    `${touchesText(zone.touches)} · ${shareText(zone.touches, total)} of all`,
    zonePlace(zone),
  ];
}

/** Where the tooltip of a zone goes: at its centre, on the side with more room. */
export function tooltipPlace(zone: Zone): TooltipPlace {
  const centre = toPitchPoint((zone.zone_x + 0.5) * ZONE_SIZE, (zone.zone_y + 0.5) * ZONE_SIZE);
  return tooltipPlaceAt(centre, ZONE_SIZE / 2, "full");
}
