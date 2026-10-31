"use client";

import { useRef, useState, type KeyboardEvent, type Ref } from "react";

import { ChartTitle } from "@/components/charts/chart-title";
import { Pitch } from "@/components/charts/pitch";
import { PitchTooltip } from "@/components/charts/pitch-tooltip";
import {
  PASS_KINDS,
  PASS_LABELS,
  passKind,
  passLabel,
  summaryText,
  tooltipLines,
  tooltipPlace,
  withoutKinds,
  type Pass,
  type PassKind,
  type PassMapSpec,
} from "@/lib/pass-map";
import { toPitchPoint } from "@/lib/pitch";
import { nextIndex } from "@/lib/shot-map";
import { cn } from "@/lib/utils";

const STROKE = { strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" } as const;
// An incomplete pass is dashed, so the kinds differ without colour.
const DASH = "4 3";
// A thin line is hard to hit, so each arrow takes the pointer in this width, in pixels.
const HIT_WIDTH = 10;
// The arrowhead and the start dot, in pitch units.
const HEAD = 2.4;
const START_RADIUS = 0.7;

const KIND_CLASS: Record<PassKind, { stroke: string; fill: string }> = {
  completed: { stroke: "stroke-brand", fill: "fill-brand" },
  incomplete: { stroke: "stroke-foreground-2", fill: "fill-foreground-2" },
};

function markerId(chartId: string, kind: PassKind): string {
  return `${chartId}-${kind}-head`;
}

/** One arrowhead marker for each kind. A marker does not take the colour of its line in each browser. */
function ArrowHeads({ chartId }: { chartId: string }) {
  return (
    <defs>
      {PASS_KINDS.map((kind) => (
        <marker
          key={kind}
          id={markerId(chartId, kind)}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerUnits="userSpaceOnUse"
          markerWidth={HEAD}
          markerHeight={HEAD}
          orient="auto"
        >
          <path d="M0 0L10 5L0 10z" className={KIND_CLASS[kind].fill} />
        </marker>
      ))}
    </defs>
  );
}

function Arrow({ pass, chartId }: { pass: Pass; chartId: string }) {
  const kind = passKind(pass);
  const start = toPitchPoint(pass.x, pass.y);
  const end = toPitchPoint(pass.end_x, pass.end_y);
  return (
    <>
      <circle cx={start.x} cy={start.y} r={START_RADIUS} className={KIND_CLASS[kind].fill} />
      <line
        x1={start.x}
        y1={start.y}
        x2={end.x}
        y2={end.y}
        markerEnd={`url(#${markerId(chartId, kind)})`}
        className={KIND_CLASS[kind].stroke}
        strokeDasharray={kind === "incomplete" ? DASH : undefined}
        {...STROKE}
      />
    </>
  );
}

type LegendProps = {
  // The kinds that the chart has arrows for.
  kinds: PassKind[];
  hidden: ReadonlySet<PassKind>;
  onToggle: (kind: PassKind) => void;
  onShowAll: () => void;
  firstRef: Ref<HTMLButtonElement>;
};

/** The legend is also the filter: each kind is a button that shows or hides its arrows. */
function Legend({ kinds, hidden, onToggle, onShowAll, firstRef }: LegendProps) {
  return (
    <ul
      aria-label="Legend"
      className="flex flex-wrap items-center gap-x-5 text-sm text-foreground-2"
    >
      {kinds.map((kind, index) => {
        const off = hidden.has(kind);
        return (
          <li key={kind}>
            <button
              ref={index === 0 ? firstRef : undefined}
              type="button"
              aria-pressed={!off}
              onClick={() => onToggle(kind)}
              // The line through the label shows the state without colour.
              className={cn(
                "flex min-h-target cursor-pointer items-center gap-2 hover:text-foreground",
                off && "text-faint line-through",
              )}
            >
              <svg
                aria-hidden="true"
                width="24"
                height="16"
                viewBox="0 0 24 16"
                className={cn(off && "opacity-40")}
              >
                <line
                  x1="2"
                  y1="8"
                  x2="16"
                  y2="8"
                  strokeWidth="1.5"
                  strokeDasharray={kind === "incomplete" ? DASH : undefined}
                  className={KIND_CLASS[kind].stroke}
                />
                <path d="M15 4L22 8L15 12z" className={KIND_CLASS[kind].fill} />
              </svg>
              {PASS_LABELS[kind]}
            </button>
          </li>
        );
      })}
      {/* With every kind on, there is nothing to show again. */}
      {hidden.size > 0 && (
        <li>
          <button
            type="button"
            onClick={onShowAll}
            className="flex min-h-target cursor-pointer items-center hover:text-foreground"
          >
            Show all
          </button>
        </li>
      )}
    </ul>
  );
}

/**
 * The passes of one player as arrows on the full pitch, from the start of each
 * pass to its end. It goes inside the figure of ChartPanel. The chart is one
 * tab stop, and the arrow keys move between the passes.
 */
export function PassMap({ chart }: { chart: PassMapSpec }) {
  const marks = useRef<(SVGGElement | null)[]>([]);
  const firstLegendButton = useRef<HTMLButtonElement>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  // The arrow that Tab goes to: the last one that had the focus.
  const [tabStop, setTabStop] = useState(0);
  const [tooltipHidden, setTooltipHidden] = useState(false);
  // The kinds that the visitor turned off in the legend.
  const [hiddenKinds, setHiddenKinds] = useState<ReadonlySet<PassKind>>(new Set());

  if (chart.passes.length === 0) {
    return (
      <>
        <ChartTitle>{chart.title}</ChartTitle>
        <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
          This chart has no passes.
        </figcaption>
      </>
    );
  }

  const chartKinds = new Set(chart.passes.map(passKind));
  // The arrows on the pitch, which the indexes below count.
  const passes = withoutKinds(chart.passes, hiddenKinds);
  const active = hovered ?? focused;
  const activePass = active === null ? null : passes[active];

  function showKinds(next: ReadonlySet<PassKind>) {
    setHiddenKinds(next);
    // The indexes count the visible arrows, so an old index is a different pass.
    setHovered(null);
    setFocused(null);
    setTabStop(0);
    setTooltipHidden(false);
  }

  function toggleKind(kind: PassKind) {
    const next = new Set(hiddenKinds);
    if (!next.delete(kind)) next.add(kind);
    showKinds(next);
  }

  function showAll() {
    showKinds(new Set());
    // Show all goes away after the click, so the focus must not fall to the page.
    firstLegendButton.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "Escape") {
      setTooltipHidden(true);
      return;
    }
    const next = nextIndex(event.key, tabStop, passes.length);
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
          aria-label={`${chart.title}. ${passes.length} ${passes.length === 1 ? "pass" : "passes"} on the pitch. Use the arrow keys to move between the passes.`}
          onKeyDown={onKeyDown}
        >
          <ArrowHeads chartId={chart.id} />
          {passes.map((pass, index) => {
            const start = toPitchPoint(pass.x, pass.y);
            const end = toPitchPoint(pass.end_x, pass.end_y);
            return (
              <g
                key={index}
                ref={(mark) => {
                  marks.current[index] = mark;
                }}
                role="img"
                aria-label={passLabel(pass)}
                tabIndex={index === tabStop ? 0 : -1}
                // The line below is the focus indicator. Browsers draw an
                // outline on a part of an SVG in different ways.
                className="cursor-pointer outline-hidden"
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
              >
                <line
                  x1={start.x}
                  y1={start.y}
                  x2={end.x}
                  y2={end.y}
                  className="stroke-transparent"
                  strokeWidth={HIT_WIDTH}
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
                <Arrow pass={pass} chartId={chart.id} />
              </g>
            );
          })}
          {activePass && (
            <line
              x1={toPitchPoint(activePass.x, activePass.y).x}
              y1={toPitchPoint(activePass.x, activePass.y).y}
              x2={toPitchPoint(activePass.end_x, activePass.end_y).x}
              y2={toPitchPoint(activePass.end_x, activePass.end_y).y}
              className="pointer-events-none stroke-ring"
              {...STROKE}
              strokeWidth={4}
              strokeLinecap="round"
            />
          )}
          {/* The active arrow is drawn again on top, so other arrows do not cover it. */}
          {activePass && (
            <g className="pointer-events-none">
              <Arrow pass={activePass} chartId={chart.id} />
            </g>
          )}
        </Pitch>
        {activePass && !tooltipHidden && (
          <PitchTooltip place={tooltipPlace(activePass)} lines={tooltipLines(activePass)} />
        )}
      </div>
      <Legend
        kinds={PASS_KINDS.filter((kind) => chartKinds.has(kind))}
        hidden={hiddenKinds}
        onToggle={toggleKind}
        onShowAll={showAll}
        firstRef={firstLegendButton}
      />
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart.passes)}
      </figcaption>
    </>
  );
}
