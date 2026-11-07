"use client";

import type { CSSProperties, ReactNode } from "react";

import styles from "@/components/ask/gallery.module.css";
import { SectionHead } from "@/components/ask/section-head";
import { TryLink } from "@/components/ask/try-link";
import { usePlayOnce } from "@/components/ask/use-play-once";
import { ShotMark } from "@/components/charts/shot-map";
import {
  barShare,
  metricLabel,
  summaryText as compareSummary,
  valueText,
  type CompareBarsSpec,
} from "@/lib/compare-bars";
import {
  ZONE_SIZE,
  summaryText as heatmapSummary,
  zoneOpacity,
  type HeatmapSpec,
} from "@/lib/heatmap";
import { LANDING_DATA, type GalleryTile } from "@/lib/landing-data";
import { passKind, summaryText as passMapSummary, type PassMapSpec } from "@/lib/pass-map";
import {
  defaultMinPasses,
  linkStyle,
  links,
  nodeRadius,
  summaryText as networkSummary,
  visibleLinks,
  type PassNetworkSpec,
} from "@/lib/pass-network";
import {
  CIRCLE_RADIUS,
  GOAL,
  PENALTY_AREA,
  PITCH_LENGTH,
  PITCH_WIDTH,
  SIX_YARD_BOX,
} from "@/lib/pitch";
import {
  lineColours,
  linePath as paceLinePath,
  scalesOf as paceScales,
  summaryText as paceSummary,
  VIEW as PACE_VIEW,
  type PointsPaceSpec,
} from "@/lib/points-pace";
import {
  drawOrder,
  outcomeKind,
  shotRadius,
  summaryText as shotSummary,
  type ShotMapSpec,
} from "@/lib/shot-map";
import { cn } from "@/lib/utils";
import {
  GOAL_RADIUS,
  endMinute,
  linePath as timelinePath,
  scalesOf as timelineScales,
  stepPoints,
  summaryText as timelineSummary,
  VIEW as TIMELINE_VIEW,
  type XgTimelineSpec,
} from "@/lib/xg-timeline";

// The longest build-up (the xG timeline and the pass map) ends at about 2 s.
const PLAY_MS = 2200;
// The marks of a chart arrive within this time, however many there are.
const SPREAD_MS = 1200;

/** The delay of mark index of count marks, so the last one starts by SPREAD_MS. */
function delay(index: number, count: number, start = 0, step = 150): CSSProperties {
  const each = Math.min(step, SPREAD_MS / Math.max(count, 1));
  return { "--d": `${Math.round(start + index * each)}ms` } as CSSProperties;
}

// A pitch on its side, with the attack to the right, as a tile is wider than tall.
// One unit is one pitch unit of the data, so a row's x and y are drawn as they are.
const LINE = { fill: "none", strokeWidth: 1, vectorEffect: "non-scaling-stroke" } as const;
const MID = PITCH_WIDTH / 2;

function PitchEnd({ flip = false }: { flip?: boolean }) {
  return (
    <g transform={flip ? `translate(${PITCH_LENGTH} 0) scale(-1 1)` : undefined}>
      <rect
        x={PITCH_LENGTH - PENALTY_AREA.depth}
        y={MID - PENALTY_AREA.width / 2}
        width={PENALTY_AREA.depth}
        height={PENALTY_AREA.width}
        {...LINE}
      />
      <rect
        x={PITCH_LENGTH - SIX_YARD_BOX.depth}
        y={MID - SIX_YARD_BOX.width / 2}
        width={SIX_YARD_BOX.depth}
        height={SIX_YARD_BOX.width}
        {...LINE}
      />
      <rect
        x={PITCH_LENGTH}
        y={MID - GOAL.width / 2}
        width={GOAL.depth}
        height={GOAL.width}
        {...LINE}
      />
    </g>
  );
}

function SidePitch({
  viewBox = "-2 -2 124 84",
  label,
  children,
}: {
  viewBox?: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <svg viewBox={viewBox} role="img" aria-label={label} className="block size-full">
      <rect x="-10" y="-10" width={PITCH_LENGTH + 20} height={PITCH_WIDTH + 20} className="fill-pitch" />
      <g className="stroke-pitch-line">
        <rect x="0" y="0" width={PITCH_LENGTH} height={PITCH_WIDTH} {...LINE} />
        <line x1={PITCH_LENGTH / 2} y1="0" x2={PITCH_LENGTH / 2} y2={PITCH_WIDTH} {...LINE} />
        <circle cx={PITCH_LENGTH / 2} cy={MID} r={CIRCLE_RADIUS} {...LINE} />
        <PitchEnd />
        <PitchEnd flip />
      </g>
      {children}
    </svg>
  );
}

const TILE_SHOT_SCALE = 0.6;

function ShotTile({ chart }: { chart: ShotMapSpec }) {
  const shots = drawOrder(chart.shots);
  return (
    // The attacking third: nearly every shot is in it, and the marks need the room.
    <SidePitch viewBox="72 16 48 32" label={`${chart.title}. ${shotSummary(chart.shots)}`}>
      {shots.map((shot, index) => (
        <g key={index} transform={`translate(${shot.x} ${shot.y})`}>
          <g style={delay(index, shots.length)} className={styles.mark}>
            {/* A season of shots in a small tile: smaller marks, the same size order. */}
            <ShotMark kind={outcomeKind(shot.outcome)} r={shotRadius(shot.xg) * TILE_SHOT_SCALE} />
          </g>
        </g>
      ))}
    </SidePitch>
  );
}

function HeatmapTile({ chart }: { chart: HeatmapSpec }) {
  const most = Math.max(...chart.zones.map((zone) => zone.touches));
  return (
    <SidePitch label={`${chart.title}. ${heatmapSummary(chart)}`}>
      {chart.zones.map((zone, index) => (
        <rect
          key={`${zone.zone_x} ${zone.zone_y}`}
          x={zone.zone_x * ZONE_SIZE}
          y={zone.zone_y * ZONE_SIZE}
          width={ZONE_SIZE}
          height={ZONE_SIZE}
          style={{ ...delay(index, chart.zones.length, 0, 70), opacity: zoneOpacity(zone.touches, most) }}
          className={cn(styles.pop, "fill-brand")}
        />
      ))}
    </SidePitch>
  );
}

function PassMapTile({ chart }: { chart: PassMapSpec }) {
  return (
    <SidePitch label={`${chart.title}. ${passMapSummary(chart.passes)}`}>
      {chart.passes.map((pass, index) => {
        const completed = passKind(pass) === "completed";
        return (
          <line
            key={index}
            x1={pass.x}
            y1={pass.y}
            x2={pass.end_x}
            y2={pass.end_y}
            pathLength={1}
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
            style={delay(index, chart.passes.length, 0, 70)}
            className={cn(
              styles.draw,
              completed ? "stroke-brand/70" : "stroke-foreground-2/40",
            )}
          />
        );
      })}
    </SidePitch>
  );
}

function NetworkTile({ chart }: { chart: PassNetworkSpec }) {
  const all = links(chart);
  const minPasses = defaultMinPasses(all);
  const shown = visibleLinks(all, minPasses);
  const at = new Map(chart.nodes.map((node) => [node.player, node]));
  const most = Math.max(...chart.nodes.map((node) => node.passes));
  const mostLink = Math.max(1, ...shown.map((link) => link.passes));
  return (
    <SidePitch label={`${chart.title}. ${networkSummary(chart, minPasses)}`}>
      {shown.map((link, index) => {
        const a = at.get(link.a);
        const b = at.get(link.b);
        if (!a || !b) return null;
        const { width, opacity } = linkStyle(link.passes, mostLink);
        return (
          <line
            key={`${link.a} ${link.b}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            pathLength={1}
            // The tile is a third of the size of an answer chart.
            strokeWidth={width * 0.6}
            vectorEffect="non-scaling-stroke"
            style={{ ...delay(index, shown.length, 200, 60), opacity }}
            className={cn(styles.draw, "stroke-foreground")}
          />
        );
      })}
      {chart.nodes.map((node, index) => (
        <circle
          key={node.player}
          cx={node.x}
          cy={node.y}
          r={nodeRadius(node.passes, most)}
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
          style={delay(index, chart.nodes.length, 0, 50)}
          className={cn(styles.pop, "fill-brand stroke-background")}
        />
      ))}
    </SidePitch>
  );
}

const TEAM_STROKE = ["stroke-brand", "stroke-foreground"];
const TEAM_FILL = ["fill-brand", "fill-foreground"];

function TimelineTile({ chart }: { chart: XgTimelineSpec }) {
  const scales = timelineScales(chart);
  const end = endMinute(chart);
  const goals = chart.teams.flatMap((team, teamIndex) =>
    team.shots.filter((shot) => shot.is_goal).map((shot) => ({ shot, teamIndex })),
  );
  return (
    <svg
      viewBox={`0 0 ${TIMELINE_VIEW.width} ${TIMELINE_VIEW.height}`}
      role="img"
      aria-label={`${chart.title}. ${timelineSummary(chart)}`}
      className="block size-full bg-surface-chart"
    >
      {chart.teams.map((team, teamIndex) => (
        <path
          key={team.team}
          d={timelinePath(stepPoints(team, end), scales)}
          pathLength={1}
          strokeWidth={2.5}
          vectorEffect="non-scaling-stroke"
          style={delay(teamIndex, chart.teams.length, 0, 120)}
          className={cn(styles.trace, "fill-none", TEAM_STROKE[teamIndex])}
        />
      ))}
      {goals.map(({ shot, teamIndex }, index) => (
        <circle
          key={index}
          cx={scales.x(shot.minute)}
          cy={scales.y(shot.total)}
          r={GOAL_RADIUS * 1.6}
          style={delay(index, goals.length, 900, 120)}
          className={cn(styles.pop, TEAM_FILL[teamIndex], "stroke-surface-chart")}
          strokeWidth={3}
        />
      ))}
    </svg>
  );
}

const PACE_STROKE = [
  "stroke-chart-1",
  "stroke-chart-2",
  "stroke-chart-3",
  "stroke-chart-4",
  "stroke-chart-5",
];
const PACE_FILL = ["fill-chart-1", "fill-chart-2", "fill-chart-3", "fill-chart-4", "fill-chart-5"];

function PaceTile({ chart }: { chart: PointsPaceSpec }) {
  const scales = paceScales(chart);
  const colours = lineColours(chart);
  return (
    <svg
      viewBox={`0 0 ${PACE_VIEW.width} ${PACE_VIEW.height}`}
      role="img"
      aria-label={`${chart.title}. ${paceSummary(chart)}`}
      className="block size-full bg-surface-chart"
    >
      {chart.lines.map((line, index) => {
        const last = line.matches.at(-1);
        return (
          <g key={`${line.team} ${line.season}`}>
            <path
              d={paceLinePath(line, scales)}
              pathLength={1}
              strokeWidth={2.5}
              vectorEffect="non-scaling-stroke"
              style={delay(index, chart.lines.length, 0, 120)}
              className={cn(styles.trace, "fill-none", PACE_STROKE[colours[index]])}
            />
            {last && (
              <circle
                cx={scales.x(last.matchday)}
                cy={scales.y(last.total)}
                r={9}
                style={delay(index, chart.lines.length, 900, 120)}
                className={cn(styles.pop, PACE_FILL[colours[index]])}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}

function CompareTile({ chart }: { chart: CompareBarsSpec }) {
  const [left, right] = chart.series;
  const rowHeight = 18;
  return (
    <svg
      viewBox="0 0 120 80"
      role="img"
      aria-label={`${chart.title}. ${compareSummary(chart)}`}
      className="block size-full bg-surface-chart"
    >
      <text x="8" y="12" className="fill-foreground font-display text-[6px] font-extrabold uppercase">
        {left.player.split(" ").at(-1)}
      </text>
      <text
        x="112"
        y="12"
        textAnchor="end"
        className="fill-brand font-display text-[6px] font-extrabold uppercase"
      >
        {right.player.split(" ").at(-1)}
      </text>
      {chart.metrics.map((metric, index) => {
        const y = 26 + index * rowHeight;
        const max = Math.max(...metric.values);
        const [a, b] = metric.values.map((value) => (barShare(value, max) / 100) * 34);
        return (
          <g key={metric.name}>
            <text x="60" y={y - 3} textAnchor="middle" className="fill-muted-foreground text-[4px]">
              {metricLabel(metric.name)}
            </text>
            <rect
              x={58 - a}
              y={y}
              width={a}
              height="4.5"
              rx="1"
              style={delay(index, chart.metrics.length, 150, 140)}
              className={cn(styles.barStart, "fill-foreground")}
            />
            <rect
              x="62"
              y={y}
              width={b}
              height="4.5"
              rx="1"
              style={delay(index, chart.metrics.length, 150, 140)}
              className={cn(styles.barEnd, "fill-brand")}
            />
            <text x={56 - a} y={y + 4} textAnchor="end" className="fill-foreground text-[4.6px] font-bold tabular-nums">
              {valueText(metric.values[0])}
            </text>
            <text x={64 + b} y={y + 4} className="fill-foreground text-[4.6px] font-bold tabular-nums">
              {valueText(metric.values[1])}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function TileChart({ chart }: { chart: GalleryTile["chart"] }) {
  switch (chart.type) {
    case "shot_map":
      return <ShotTile chart={chart} />;
    case "heatmap":
      return <HeatmapTile chart={chart} />;
    case "pass_map":
      return <PassMapTile chart={chart} />;
    case "pass_network":
      return <NetworkTile chart={chart} />;
    case "xg_timeline":
      return <TimelineTile chart={chart} />;
    case "points_pace":
      return <PaceTile chart={chart} />;
    case "compare_bars":
      return <CompareTile chart={chart} />;
  }
}

// The name of each chart type, as the tile shows it.
const CHART_NAMES: Record<GalleryTile["chart"]["type"], string> = {
  shot_map: "Shot map",
  heatmap: "Touch heatmap",
  pass_map: "Pass map",
  pass_network: "Pass network",
  xg_timeline: "xG timeline",
  points_pace: "Points pace",
  compare_bars: "Compare bars",
};

function Tile({ tile, onTry }: { tile: GalleryTile; onTry: (question: string) => void }) {
  const { ref, playing, onPointerEnter, onFocus } = usePlayOnce(PLAY_MS);
  return (
    <article
      ref={ref}
      onPointerEnter={onPointerEnter}
      onFocus={onFocus}
      className={cn(
        // Eight columns: four tiles, then three that start one column in, so they are centred.
        "col-span-2 grid grid-rows-[auto_1fr_auto] gap-3.5 rounded-2xl border bg-card px-2 pt-2 pb-3.5 transition-[border-color] duration-200 hover:border-line-strong",
        "nth-5:col-start-2 max-[1080px]:nth-5:col-start-auto max-[1080px]:nth-7:col-start-3",
        "max-[760px]:col-span-1 max-[760px]:nth-7:col-span-2 max-[760px]:nth-7:col-start-1 max-[760px]:nth-7:w-[calc(50%-6px)] max-[760px]:nth-7:justify-self-center",
        playing && styles.play,
      )}
    >
      <div className="aspect-[3/2] overflow-hidden rounded-[10px] border border-line-subtle">
        <TileChart chart={tile.chart} />
      </div>
      <div className="flex items-baseline justify-between gap-2.5 px-2 max-[760px]:flex-col max-[760px]:gap-1">
        <h3 className="font-sans text-[17px] leading-tight font-semibold max-[760px]:text-[15px]">
          {CHART_NAMES[tile.chart.type]}
        </h3>
        <span className="shrink-0 font-mono text-[11px] leading-none font-medium tracking-[0.06em] text-muted-foreground uppercase">
          {tile.season}
        </span>
      </div>
      <TryLink
        label={tile.label}
        question={tile.question}
        onTry={onTry}
        className="mx-2 text-sm max-[760px]:text-[13px]"
      />
    </article>
  );
}

export const GALLERY = {
  headline: ["Seven ways", "to see a season."] as const,
  lead: "Every chart below is drawn from real rows. Pick one, and the question that makes it goes into the box.",
};

/** Seven charts of real rows, one of each type, each with the golden question that makes it. */
export function Gallery({ onTry }: { onTry: (question: string) => void }) {
  return (
    <section
      aria-labelledby="gallery-title"
      className="mx-auto w-full max-w-[1200px] pb-30 max-[600px]:pb-22"
    >
      <SectionHead id="gallery-title" headline={GALLERY.headline} lead={GALLERY.lead} />
      <div className="grid grid-cols-8 gap-5 max-[1080px]:grid-cols-6 max-[760px]:grid-cols-2 max-[760px]:gap-3">
        {LANDING_DATA.tiles.map((tile) => (
          <Tile key={tile.id} tile={tile} onTry={onTry} />
        ))}
      </div>
    </section>
  );
}
