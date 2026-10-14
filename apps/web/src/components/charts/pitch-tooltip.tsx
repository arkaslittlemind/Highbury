import type { TooltipPlace } from "@/lib/pitch";
import { cn } from "@/lib/utils";

// The width of the tooltip: w-52.
const TOOLTIP_WIDTH = "13rem";

/** The tooltip of a mark on a pitch chart. The first line is the heading. */
export function PitchTooltip({ place, lines }: { place: TooltipPlace; lines: string[] }) {
  const [heading, ...rest] = lines;
  return (
    // The label of the mark has the same text, so a screen reader does not need this.
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute z-10 w-52 rounded-lg bg-foreground px-3.5 py-3 text-sm leading-snug text-background shadow-pop",
        place.side === "below" ? "mt-2" : "mb-2",
      )}
      // The place comes from the data of the mark, so it cannot be a class.
      // clamp() keeps the tooltip inside the drawing.
      style={{
        left: `clamp(0px, calc(${place.left}% - ${TOOLTIP_WIDTH} / 2), calc(100% - ${TOOLTIP_WIDTH}))`,
        ...(place.side === "below"
          ? { top: `${place.top}%` }
          : { bottom: `${100 - place.top}%` }),
      }}
    >
      <div className="font-bold">{heading}</div>
      {rest.map((line, index) => (
        <div key={index} className={cn(index > 0 && "text-tooltip-muted")}>
          {line}
        </div>
      ))}
    </div>
  );
}
