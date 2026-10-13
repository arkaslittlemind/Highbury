import type { ComponentProps } from "react";

import {
  CIRCLE_RADIUS,
  GOAL,
  PENALTY_AREA,
  PENALTY_SPOT_DISTANCE,
  PITCH_LENGTH,
  PITCH_WIDTH,
  SIX_YARD_BOX,
  viewBoxOf,
  viewLength,
  type PitchView,
} from "@/lib/pitch";
import { cn } from "@/lib/utils";

const CENTRE = PITCH_WIDTH / 2;

// A line keeps its width on the screen at each size of the drawing.
const LINE = {
  fill: "none",
  strokeWidth: 1.5,
  vectorEffect: "non-scaling-stroke",
} as const;

/** The markings of one end, with the goal line at y = 0 and the pitch below it. */
function PitchEnd(props: ComponentProps<"g">) {
  // Half of the part of the arc that is outside the penalty area.
  const arcHalfWidth = Math.sqrt(
    CIRCLE_RADIUS ** 2 - (PENALTY_AREA.depth - PENALTY_SPOT_DISTANCE) ** 2,
  );
  return (
    <g {...props}>
      <rect
        x={CENTRE - PENALTY_AREA.width / 2}
        y={0}
        width={PENALTY_AREA.width}
        height={PENALTY_AREA.depth}
        {...LINE}
      />
      <rect
        x={CENTRE - SIX_YARD_BOX.width / 2}
        y={0}
        width={SIX_YARD_BOX.width}
        height={SIX_YARD_BOX.depth}
        {...LINE}
      />
      <rect
        x={CENTRE - GOAL.width / 2}
        y={-GOAL.depth}
        width={GOAL.width}
        height={GOAL.depth}
        className="stroke-foreground-2"
        {...LINE}
      />
      <circle
        cx={CENTRE}
        cy={PENALTY_SPOT_DISTANCE}
        r={0.4}
        className="fill-pitch-line stroke-none"
      />
      <path
        d={`M${CENTRE - arcHalfWidth} ${PENALTY_AREA.depth} A${CIRCLE_RADIUS} ${CIRCLE_RADIUS} 0 0 0 ${CENTRE + arcHalfWidth} ${PENALTY_AREA.depth}`}
        {...LINE}
      />
    </g>
  );
}

type PitchProps = { view: PitchView } & Omit<ComponentProps<"svg">, "viewBox">;

/**
 * A football pitch with the attack going up the screen. One SVG unit is one
 * pitch unit, so a child is placed with toPitchPoint and needs no more scaling.
 */
export function Pitch({ view, className, children, ...props }: PitchProps) {
  const box = viewBoxOf(view);
  const length = viewLength(view);
  const halfway = PITCH_LENGTH / 2;
  return (
    <svg
      viewBox={`${box.minX} ${box.minY} ${box.width} ${box.height}`}
      // A large mark on a touchline goes past the view box, and must not be cut.
      className={cn("block h-auto w-full overflow-visible", className)}
      {...props}
    >
      <g className="stroke-pitch-line">
        <rect x={0} y={0} width={PITCH_WIDTH} height={length} className="fill-pitch" {...LINE} />
        <PitchEnd />
        {view === "full" ? (
          <>
            <line x1={0} y1={halfway} x2={PITCH_WIDTH} y2={halfway} {...LINE} />
            <circle cx={CENTRE} cy={halfway} r={CIRCLE_RADIUS} {...LINE} />
            <circle cx={CENTRE} cy={halfway} r={0.4} className="fill-pitch-line stroke-none" />
            <PitchEnd transform={`translate(0 ${PITCH_LENGTH}) scale(1 -1)`} />
          </>
        ) : (
          <path
            d={`M${CENTRE - CIRCLE_RADIUS} ${halfway} A${CIRCLE_RADIUS} ${CIRCLE_RADIUS} 0 0 1 ${CENTRE + CIRCLE_RADIUS} ${halfway}`}
            {...LINE}
          />
        )}
      </g>
      {children}
    </svg>
  );
}
