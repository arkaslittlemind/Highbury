"use client";

import { useId, useRef, useState, type KeyboardEvent } from "react";

import { SummaryChevron } from "@/components/ask/summary-chevron";
import { ChartTitle } from "@/components/charts/chart-title";
import { Pitch } from "@/components/charts/pitch";
import { PitchTooltip } from "@/components/charts/pitch-tooltip";
import {
  defaultMinPasses,
  LABEL_SIZE,
  labelOffset,
  labelSides,
  linkStyle,
  links,
  nodeLabel,
  nodeOrder,
  nodeRadius,
  nodeTooltipPlace,
  shortName,
  summaryText,
  tooltipLines,
  visibleLinks,
  windowText,
  type Link,
  type PassNetworkSpec,
  type PassNode,
} from "@/lib/pass-network";
import { toPitchPoint } from "@/lib/pitch";
import { nextIndex } from "@/lib/shot-map";

// A small node is hard to hit, so each node takes the pointer in this radius or more.
const MIN_HIT_RADIUS = 3;
// The ring of the active node is this far outside the node, in pitch units.
const RING_GAP = 0.8;

const STROKE = { strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" } as const;

function Legend() {
  return (
    <ul
      aria-label="Legend"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-foreground-2"
    >
      <li className="flex min-h-target items-center gap-2">
        <svg aria-hidden="true" width="40" height="16" viewBox="0 0 40 16">
          <circle cx="5" cy="8" r="2.5" className="fill-brand" />
          <circle cx="17" cy="8" r="4.5" className="fill-brand" />
          <circle cx="32" cy="8" r="7" className="fill-brand" />
        </svg>
        Fewer → more passes made
      </li>
      <li className="flex min-h-target items-center gap-2">
        <svg aria-hidden="true" width="40" height="16" viewBox="0 0 40 16">
          <line x1="2" y1="4" x2="38" y2="4" strokeWidth="1" className="stroke-foreground/40" />
          <line x1="2" y1="11" x2="38" y2="11" strokeWidth="4" className="stroke-foreground/90" />
        </svg>
        Line = passes between two players
      </li>
    </ul>
  );
}

type LinkLinesProps = {
  links: Link[];
  positions: Map<string, { x: number; y: number }>;
  // The player whose links stand out, or null for none.
  active: string | null;
};

function LinkLines({ links: allLinks, positions, active }: LinkLinesProps) {
  const maxPasses = allLinks[0]?.passes ?? 1;
  // The weakest first, so that a strong line is on top.
  const order = [...allLinks].reverse();
  return (
    <g aria-hidden="true" className="pointer-events-none">
      {order.map((link) => {
        const from = positions.get(link.a);
        const to = positions.get(link.b);
        if (!from || !to) return null;
        const style = linkStyle(link.passes, maxPasses);
        const touches = active !== null && (link.a === active || link.b === active);
        const opacity = active === null ? style.opacity : touches ? 0.95 : 0.08;
        return (
          <line
            key={`${link.a}\n${link.b}`}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            strokeWidth={style.width}
            strokeOpacity={opacity}
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
            className={touches ? "stroke-brand" : "stroke-foreground"}
          />
        );
      })}
    </g>
  );
}

type MinPassesProps = {
  value: number;
  // The most passes on one link: a higher minimum would hide every line.
  max: number;
  shown: number;
  total: number;
  onChange: (value: number) => void;
};

/** The minimum of passes for a line to be drawn. Weak links hide the shape of the team. */
function MinPasses({ value, max, shown, total, onChange }: MinPassesProps) {
  const id = useId();
  return (
    <div className="flex min-h-target flex-wrap items-center gap-x-3 gap-y-1 text-sm text-foreground-2">
      <label htmlFor={id}>Minimum passes per link</label>
      <input
        id={id}
        type="range"
        min={1}
        max={max}
        step={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-36 cursor-pointer accent-brand"
      />
      <output htmlFor={id} className="w-6 font-mono text-foreground">
        {value}
      </output>
      <span className="text-muted-foreground">
        {shown} of {total} links shown
      </span>
    </div>
  );
}

const CELL = "border-t border-line-subtle px-2 py-2 first:pl-0 last:pr-0";

/** The drawn links as a table: the same rows, in the same order, as the lines. */
function LinkTable({ drawn, minPasses }: { drawn: Link[]; minPasses: number }) {
  return (
    <details className="group rounded-panel border bg-surface-sunken">
      <summary className="flex min-h-target cursor-pointer list-none items-center gap-3 px-5 py-3">
        <span className="flex flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <span className="font-semibold text-foreground">Show the data</span>
          <span className="text-sm text-muted-foreground">
            {drawn.length} {drawn.length === 1 ? "link" : "links"}
          </span>
        </span>
        <SummaryChevron />
      </summary>
      {/* Five columns do not fit a phone, so the table scrolls inside its box. */}
      <div className="overflow-x-auto px-5 pb-4">
        <table className="w-full text-left text-sm tabular-nums">
          <caption className="pb-2 text-left text-muted-foreground">
            The passing links on the pitch, each with at least {minPasses}{" "}
            {minPasses === 1 ? "pass" : "passes"}.
          </caption>
          <thead className="text-foreground">
            <tr>
              <th scope="col" className={CELL}>
                Player
              </th>
              <th scope="col" className={CELL}>
                Partner
              </th>
              <th scope="col" className={`${CELL} text-right`}>
                To partner
              </th>
              <th scope="col" className={`${CELL} text-right`}>
                From partner
              </th>
              <th scope="col" className={`${CELL} text-right`}>
                Total
              </th>
            </tr>
          </thead>
          <tbody className="text-foreground-2">
            {drawn.length === 0 ? (
              <tr>
                <td colSpan={5} className={CELL}>
                  No link has this many passes.
                </td>
              </tr>
            ) : (
              drawn.map((link) => (
                <tr key={`${link.a}
${link.b}`}>
                  <th scope="row" className={`${CELL} font-normal`}>
                    {link.a}
                  </th>
                  <td className={CELL}>{link.b}</td>
                  <td className={`${CELL} text-right`}>{link.aToB}</td>
                  <td className={`${CELL} text-right`}>{link.bToA}</td>
                  <td className={`${CELL} text-right font-semibold text-foreground`}>
                    {link.passes}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/** The names on the pitch, above all the nodes, so that no node hides a name. */
function Names({ nodes, maxPasses }: { nodes: PassNode[]; maxPasses: number }) {
  const sides = labelSides(nodes, maxPasses);
  return (
    <g aria-hidden="true" className="pointer-events-none">
      {nodes.map((node) => {
        const side = sides.get(node.player);
        if (!side) return null;
        const point = toPitchPoint(node.x, node.y);
        return (
          <text
            key={node.player}
            x={point.x}
            y={point.y + labelOffset(side, nodeRadius(node.passes, maxPasses))}
            textAnchor="middle"
            fontSize={LABEL_SIZE}
            strokeWidth={0.6}
            paintOrder="stroke"
            // The stroke in the colour of the pitch keeps a name readable over a line.
            className="fill-foreground stroke-pitch font-semibold"
          >
            {shortName(node.player)}
          </text>
        );
      })}
    </g>
  );
}

/**
 * The passes of one team in one match on the full pitch: each player at the mean
 * start of their passes, sized by the passes made, with a line for each pair. It
 * goes inside the figure of ChartPanel. The chart is one tab stop, and the arrow
 * keys move between the players.
 */
export function PassNetwork({ chart }: { chart: PassNetworkSpec }) {
  const marks = useRef<(SVGGElement | null)[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [focused, setFocused] = useState<number | null>(null);
  // The node that Tab goes to: the last one that had the focus.
  const [tabStop, setTabStop] = useState(0);
  const [tooltipHidden, setTooltipHidden] = useState(false);
  const [minPasses, setMinPasses] = useState(() => defaultMinPasses(links(chart)));

  if (chart.nodes.length === 0) {
    return (
      <>
        <ChartTitle>{chart.title}</ChartTitle>
        <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
          This chart has no passes.
        </figcaption>
      </>
    );
  }

  // The most passes first: large nodes are drawn first, so a small one is not hidden.
  const nodes = nodeOrder(chart.nodes);
  // Every link describes a player in labels and tooltips. Only the drawn ones are lines.
  const allLinks = links(chart);
  const drawn = visibleLinks(allLinks, minPasses);
  const maxPasses = nodes[0].passes;
  const positions = new Map(nodes.map((node) => [node.player, toPitchPoint(node.x, node.y)]));
  const active = hovered ?? focused;
  const activeNode = active === null ? null : nodes[active];

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "Escape") {
      setTooltipHidden(true);
      return;
    }
    const next = nextIndex(event.key, tabStop, nodes.length);
    if (next === null) return;
    // An arrow key must not scroll the page.
    event.preventDefault();
    marks.current[next]?.focus();
  }

  return (
    <>
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <ChartTitle>{chart.title}</ChartTitle>
          <span className="text-sm text-muted-foreground">Attacking upward · size = passes</span>
        </div>
        <p className="text-sm text-foreground-2">{windowText(chart)}</p>
      </div>
      {/* The full pitch is tall, so its width is held to keep it in one screen. */}
      <div className="relative mx-auto w-full max-w-[440px]">
        <Pitch
          view="full"
          role="group"
          aria-label={`${chart.title}. ${nodes.length} ${nodes.length === 1 ? "player" : "players"} on the pitch. Use the arrow keys to move between the players.`}
          onKeyDown={onKeyDown}
        >
          <LinkLines links={drawn} positions={positions} active={activeNode?.player ?? null} />
          {nodes.map((node, index) => {
            const point = toPitchPoint(node.x, node.y);
            const r = nodeRadius(node.passes, maxPasses);
            return (
              <g
                key={node.player}
                ref={(mark) => {
                  marks.current[index] = mark;
                }}
                role="img"
                aria-label={nodeLabel(node, allLinks)}
                tabIndex={index === tabStop ? 0 : -1}
                transform={`translate(${point.x} ${point.y})`}
                // The ring below is the focus indicator. Browsers draw an
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
                <circle r={Math.max(r, MIN_HIT_RADIUS)} className="fill-transparent" />
                <circle r={r} className="fill-brand stroke-background" {...STROKE} />
              </g>
            );
          })}
          <Names nodes={nodes} maxPasses={maxPasses} />
          {activeNode && (
            <circle
              cx={toPitchPoint(activeNode.x, activeNode.y).x}
              cy={toPitchPoint(activeNode.x, activeNode.y).y}
              r={nodeRadius(activeNode.passes, maxPasses) + RING_GAP}
              className="pointer-events-none fill-none stroke-ring"
              {...STROKE}
              strokeWidth={3}
            />
          )}
        </Pitch>
        {activeNode && !tooltipHidden && (
          <PitchTooltip
            place={nodeTooltipPlace(activeNode, maxPasses)}
            lines={tooltipLines(activeNode, allLinks)}
          />
        )}
      </div>
      <Legend />
      {allLinks.length > 0 && (
        <MinPasses
          value={minPasses}
          max={allLinks[0].passes}
          shown={drawn.length}
          total={allLinks.length}
          onChange={setMinPasses}
        />
      )}
      <LinkTable drawn={drawn} minPasses={minPasses} />
      {/* The caption stays the last child of the figure, as HTML requires. */}
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart, minPasses)}
      </figcaption>
    </>
  );
}
