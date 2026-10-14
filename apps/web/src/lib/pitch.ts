import { scaleLinear } from "d3-scale";

// Data coordinates: 120 x 80, the attack goes from x = 0 to x = 120, and y = 0
// is the left touchline of the attacking team.
export const PITCH_LENGTH = 120;
export const PITCH_WIDTH = 80;

// Sizes of the markings, in pitch units. Depth is along the length of the pitch.
export const PENALTY_AREA = { depth: 18, width: 44 };
export const SIX_YARD_BOX = { depth: 6, width: 20 };
export const GOAL = { depth: 1.6, width: 8 };
export const PENALTY_SPOT_DISTANCE = 12;
export const CIRCLE_RADIUS = 10;

export type PitchView = "attacking-half" | "full";

export type SvgPoint = { x: number; y: number };
export type ViewBox = { minX: number; minY: number; width: number; height: number };

// The pitch is drawn with the attack going up the screen, and one SVG unit is
// one pitch unit. So the width of the pitch goes across, and the length is
// turned over: the goal line of the attack is at the top.
const across = scaleLinear().domain([0, PITCH_WIDTH]).range([0, PITCH_WIDTH]);
const down = scaleLinear().domain([0, PITCH_LENGTH]).range([PITCH_LENGTH, 0]);

/** The place on the drawing of a data coordinate. */
export function toPitchPoint(x: number, y: number): SvgPoint {
  return { x: across(y), y: down(x) };
}

// Space around the pitch. The top has room for the goal behind the goal line.
const MARGIN = { side: 2, top: 4, bottom: 2 };

/** The length of pitch that a view shows, from the goal line of the attack. */
export function viewLength(view: PitchView): number {
  return view === "full" ? PITCH_LENGTH : PITCH_LENGTH / 2;
}

export function viewBoxOf(view: PitchView): ViewBox {
  return {
    minX: -MARGIN.side,
    minY: -MARGIN.top,
    width: PITCH_WIDTH + 2 * MARGIN.side,
    height: viewLength(view) + MARGIN.top + MARGIN.bottom,
  };
}

export type TooltipPlace = {
  // The centre of the mark, as a percentage of the width of the drawing.
  left: number;
  // The edge of the mark that the tooltip touches, as a percentage of the height.
  top: number;
  side: "above" | "below";
};

/**
 * Where the tooltip of a mark goes on a view: on the side of the mark that has more
 * room, touching the mark at its reach from the point.
 */
export function tooltipPlaceAt(point: SvgPoint, reach: number, view: PitchView): TooltipPlace {
  const box = viewBoxOf(view);
  const side = point.y - box.minY < box.height / 2 ? "below" : "above";
  const edge = side === "below" ? point.y + reach : point.y - reach;
  return {
    left: ((point.x - box.minX) / box.width) * 100,
    top: ((edge - box.minY) / box.height) * 100,
    side,
  };
}

/** True for a data coordinate in the penalty area of the attack, its lines included. */
export function isInPenaltyArea(x: number, y: number): boolean {
  return (
    x >= PITCH_LENGTH - PENALTY_AREA.depth &&
    Math.abs(y - PITCH_WIDTH / 2) <= PENALTY_AREA.width / 2
  );
}
