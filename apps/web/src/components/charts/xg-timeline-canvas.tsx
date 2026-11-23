"use client";

import { ScatterChart } from "echarts/charts";
import { MarkLineComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { memo, useCallback, useMemo, useRef } from "react";

import {
  EChartsAreaChart,
  type ChartConfig,
  type EChartsInstance,
} from "@/components/evilcharts/charts/echarts-area-chart";
import { normalizeColor } from "@/components/evilcharts/ui/echarts-chart";
import {
  HALF_TIME,
  MINUTE_TICKS,
  markOrder,
  markPoints,
  minuteRows,
  tooltipHtml,
  xgAxis,
  type XgTimelineSpec,
} from "@/lib/xg-timeline";

// The area chart registers only line series. The marks are a scatter series, and
// the half-time rule is a mark line.
echarts.use([ScatterChart, MarkLineComponent]);

/** What the keyboard of the chart shell needs: show the tooltip of a mark, or hide it. */
export type TimelineApi = { show: (index: number) => void; hide: () => void };

const MARKS_ID = "marks";
// The size of a mark in pixels. A goal is larger and filled, so it shows by shape.
const SHOT_SIZE = 8;
const GOAL_SIZE = 13;
const TILE_GOAL_SIZE = 12;

const TOOLTIP_SHELL =
  "grid gap-1 rounded-md border border-border/50 bg-background px-2.5 py-1.5 text-xs leading-snug text-muted-foreground shadow-xl";

const isTick = (index: number) => MINUTE_TICKS.includes(index);

type Option = Record<string, unknown> & {
  series: Record<string, unknown>[];
  xAxis: Record<string, Record<string, unknown>>;
  yAxis: Record<string, Record<string, unknown>>;
  tooltip: Record<string, unknown>;
};

/**
 * The ECharts drawing of the xG timeline: a stepped area per team and the shots as
 * marks. It needs the window, so it loads in the client only (next/dynamic). In the
 * compact form (the gallery tile) it has no axis, no tooltip, and only the goals.
 */
function XgTimelineCanvas({
  chart,
  compact = false,
  onReady,
}: {
  chart: XgTimelineSpec;
  compact?: boolean;
  onReady?: (api: TimelineApi | null) => void;
}) {
  const rows = useMemo(() => minuteRows(chart), [chart]);
  // The marks that the chart shows: every shot, or only the goals in the compact
  // form. The scatter data and the tooltip both read this list, so a data index
  // is always the index of its mark.
  const shown = useMemo(() => {
    const points = markPoints(chart);
    const marks = markOrder(chart).map((mark, index) => ({ mark, point: points[index] }));
    return compact ? marks.filter(({ point }) => point.isGoal) : marks;
  }, [chart, compact]);
  const config = useMemo<ChartConfig>(
    () => ({
      // The site is dark only, so both themes take the same tokens.
      t0: { label: chart.teams[0].team, colors: { light: ["var(--brand)"], dark: ["var(--brand)"] } },
      t1: {
        label: chart.teams[1].team,
        colors: { light: ["var(--foreground)"], dark: ["var(--foreground)"] },
      },
    }),
    [chart],
  );
  // The place of the marks series in the pushed option, for showTip.
  const marksIndex = useRef(0);

  const chartOptions = useCallback(
    (built: Record<string, unknown>) => {
      const option = built as Option;
      const css = getComputedStyle(document.documentElement);
      // ECharts mixes colours for its states, so each token becomes plain rgba.
      const token = (name: string) => normalizeColor(css.getPropertyValue(name));
      const team = [token("--brand"), token("--foreground")];
      const surface = token("--surface-chart");
      const axis = xgAxis(chart);

      const data = shown.map(({ point }) => ({
        value: [String(point.minute), point.total],
        symbolSize: point.isGoal ? (compact ? TILE_GOAL_SIZE : GOAL_SIZE) : SHOT_SIZE,
        itemStyle: point.isGoal
          ? { color: team[point.team], borderColor: surface, borderWidth: compact ? 2.5 : 1.5 }
          : { color: surface, borderColor: team[point.team], borderWidth: 1.5 },
      }));

      const series = [
        // The jump of a step is at the minute of the shot, where its mark is.
        ...option.series.map((one) => (one.type === "line" ? { ...one, step: "end" } : one)),
        {
          id: MARKS_ID,
          type: "scatter",
          z: 5,
          data,
          cursor: compact ? "default" : "pointer",
          silent: compact,
          emphasis: { scale: false, itemStyle: { borderColor: token("--ring"), borderWidth: 3 } },
          markLine: compact
            ? undefined
            : {
                silent: true,
                symbol: "none",
                label: { show: false },
                lineStyle: { color: token("--line-mid"), type: [2, 4], width: 1 },
                data: [{ xAxis: String(HALF_TIME) }],
              },
        },
      ];
      marksIndex.current = series.length - 1;

      const xAxis = {
        ...option.xAxis,
        axisLabel: {
          ...option.xAxis.axisLabel,
          interval: isTick,
          formatter: (value: string) => (value === String(HALF_TIME) ? "HT" : `${value}'`),
        },
        axisTick: { ...option.xAxis.axisTick, interval: isTick },
      };
      const yAxis = {
        ...option.yAxis,
        min: 0,
        max: axis.max,
        interval: axis.interval,
        axisLabel: {
          ...option.yAxis.axisLabel,
          formatter: (value: number) =>
            value === 0 ? "" : value.toFixed(Number.isInteger(value * 2) ? 1 : 2),
        },
      };
      const tooltip = {
        ...option.tooltip,
        trigger: "item",
        axisPointer: { type: "none" },
        formatter: (params: { seriesId?: string; dataIndex: number }) =>
          params.seriesId === MARKS_ID
            ? `<div class="${TOOLTIP_SHELL}">${tooltipHtml(shown[params.dataIndex].mark)}</div>`
            : "",
      };
      return {
        ...option,
        ...(compact ? { grid: { left: 10, right: 10, top: 12, bottom: 10 } } : {}),
        series,
        xAxis,
        yAxis,
        tooltip,
      };
    },
    [chart, compact, shown],
  );

  const onChartReady = useCallback(
    (instance: EChartsInstance | null) => {
      if (!onReady) return;
      if (!instance) {
        onReady(null);
        return;
      }
      onReady({
        show(index) {
          instance.dispatchAction({ type: "downplay", seriesIndex: marksIndex.current });
          instance.dispatchAction({
            type: "highlight",
            seriesIndex: marksIndex.current,
            dataIndex: index,
          });
          instance.dispatchAction({
            type: "showTip",
            seriesIndex: marksIndex.current,
            dataIndex: index,
          });
        },
        hide() {
          instance.dispatchAction({ type: "downplay", seriesIndex: marksIndex.current });
          instance.dispatchAction({ type: "hideTip" });
        },
      });
    },
    [onReady],
  );

  return (
    <EChartsAreaChart
      data={rows}
      config={config}
      xDataKey="minute"
      curveType="step"
      className="size-full"
      chartOptions={chartOptions}
      onChartReady={onChartReady}
    >
      <EChartsAreaChart.Area dataKey="t1" variant="gradient" strokeVariant="dashed" strokeWidth={2} />
      <EChartsAreaChart.Area dataKey="t0" variant="gradient" strokeVariant="solid" strokeWidth={2} />
      {!compact && <EChartsAreaChart.Grid />}
      {!compact && <EChartsAreaChart.XAxis />}
      {!compact && <EChartsAreaChart.YAxis />}
      {!compact && <EChartsAreaChart.Tooltip cursor={false} />}
    </EChartsAreaChart>
  );
}

// A render of the area chart pushes a new option, which closes an open tooltip. The
// keyboard of the shell changes its own state on each arrow key, so the canvas must
// not render again unless its props change.
export default memo(XgTimelineCanvas);
