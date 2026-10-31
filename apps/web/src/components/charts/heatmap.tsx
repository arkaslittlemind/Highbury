"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import { ChartTitle } from "@/components/charts/chart-title";
import { Pitch } from "@/components/charts/pitch";
import { PitchTooltip } from "@/components/charts/pitch-tooltip";
import {
  MAX_OPACITY,
  MIN_OPACITY,
  summaryText,
  tooltipLines,
  tooltipPlace,
  zoneLabel,
  zoneOpacity,
  zoneRect,
  type HeatmapSpec,
} from "@/lib/heatmap";
import { nextIndex } from "@/lib/shot-map";

// The steps of the scale key, from the faintest shade to the strongest.
const KEY_STEPS = 5;

/** The scale key: the shade of the fewest and the most touches in one zone. */
function ScaleKey({ fewest, most }: { fewest: number; most: number }) {
  return (
    <div className="flex items-center gap-2 text-sm text-foreground-2">
      <span>
        {fewest} {fewest === 1 ? "touch" : "touches"}
      </span>
      <svg aria-hidden="true" width="100" height="12" viewBox="0 0 100 12">
        {Array.from({ length: KEY_STEPS }, (_, step) => (
          <rect
            key={step}
            x={step * 20}
            y={0}
            width={20}
            height={12}
            className="fill-brand"
            fillOpacity={MIN_OPACITY + ((MAX_OPACITY - MIN_OPACITY) * step) / (KEY_STEPS - 1)}
          />
        ))}
      </svg>
      <span>{most} in one zone</span>
    </div>
  );
}

/**
 * The touches of one player on the full pitch, counted in zones of 10 x 10. It
 * goes inside the figure of ChartPanel. The chart is one tab stop, and the arrow
 * keys move between the zones.
 */
export function Heatmap({ chart }: { chart: HeatmapSpec }) {
  const marks = useRef<(SVGRectElement | null)[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  // The zone that Tab goes to: the last one that had the focus.
  const [tabStop, setTabStop] = useState(0);
  const [tooltipHidden, setTooltipHidden] = useState(false);

  const zones = chart.zones;
  const counts = zones.map((zone) => zone.touches);
  const most = Math.max(...counts);
  const active = hovered ?? focused;
  const activeZone = active === null ? null : zones[active];

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "Escape") {
      setTooltipHidden(true);
      return;
    }
    const next = nextIndex(event.key, tabStop, zones.length);
    if (next === null) return;
    // An arrow key must not scroll the page.
    event.preventDefault();
    marks.current[next]?.focus();
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <ChartTitle>{chart.title}</ChartTitle>
        <span className="text-sm text-muted-foreground">Attacking upward</span>
      </div>
      {/* The full pitch is tall, so its width is held to keep it in one screen. */}
      <div className="relative mx-auto w-full max-w-[440px]">
        <Pitch
          view="full"
          role="group"
          aria-label={`${chart.title}. ${zones.length} ${zones.length === 1 ? "zone" : "zones"} with touches. Use the arrow keys to move between the zones.`}
          onKeyDown={onKeyDown}
        >
          {zones.map((zone, index) => (
            <rect
              key={`${zone.zone_x}-${zone.zone_y}`}
              ref={(mark) => {
                marks.current[index] = mark;
              }}
              {...zoneRect(zone)}
              role="img"
              aria-label={zoneLabel(zone, chart.total)}
              tabIndex={index === tabStop ? 0 : -1}
              // The rect below is the focus indicator. Browsers draw an outline
              // on a part of an SVG in different ways.
              className="cursor-pointer fill-brand outline-hidden"
              fillOpacity={zoneOpacity(zone.touches, most)}
              onPointerEnter={() => {
                setHovered(index);
                setTooltipHidden(false);
              }}
              onPointerLeave={() => setHovered(null)}
              onFocus={() => {
                setFocused(index);
                setTabStop(index);
                setTooltipHidden(false);
              }}
              onBlur={() => setFocused(null)}
              // A touch screen has no hover, and a tap does not always give the focus.
              onClick={(event) => event.currentTarget.focus()}
            />
          ))}
          {activeZone && (
            <rect
              {...zoneRect(activeZone)}
              className="pointer-events-none fill-none stroke-ring"
              strokeWidth={3}
              vectorEffect="non-scaling-stroke"
            />
          )}
        </Pitch>
        {activeZone && !tooltipHidden && (
          <PitchTooltip
            place={tooltipPlace(activeZone)}
            lines={tooltipLines(activeZone, chart.total)}
          />
        )}
      </div>
      <ScaleKey fewest={Math.min(...counts)} most={most} />
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart)}
      </figcaption>
    </>
  );
}
