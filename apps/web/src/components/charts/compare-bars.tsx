import { ChartTitle } from "@/components/charts/chart-title";
import {
  barShare,
  hasModelCaveat,
  isCrossSeason,
  isModelMetric,
  metricLabel,
  summaryText,
  valueText,
  type CompareBarsSpec,
  type Series,
} from "@/lib/compare-bars";
import { cn } from "@/lib/utils";

// The first player is on the left and the second one is on the right. The
// metric label is between them. The columns are narrower in a narrow panel.
const ROW = "grid grid-cols-[minmax(0,1fr)_5.5rem_minmax(0,1fr)] items-center gap-2 @md:grid-cols-[minmax(0,1fr)_10rem_minmax(0,1fr)] @md:gap-4";
const VALUE = "w-11 shrink-0 font-display text-xl font-bold @md:w-16 @md:text-[26px]";

function PlayerHeader({ series, side }: { series: Series; side: "left" | "right" }) {
  return (
    <div role="columnheader" className={cn(side === "left" && "text-right")}>
      <div
        className={cn(
          "font-display text-[26px] leading-none font-extrabold uppercase @md:text-[44px]",
          side === "right" && "text-brand",
        )}
      >
        {series.player}
      </div>
      <div className="mt-1.5 inline-flex items-center gap-2 text-sm text-foreground-2">
        <span
          aria-hidden="true"
          className={cn("size-2.5 rounded-xs", side === "left" ? "bg-foreground" : "bg-brand")}
        />
        {series.season}
      </div>
    </div>
  );
}

function Bar({ share, side }: { share: number; side: "left" | "right" }) {
  return (
    // The number next to the bar carries the value.
    <div aria-hidden="true" className={cn("flex min-w-0 flex-1", side === "left" && "justify-end")}>
      <div
        className={cn(
          "h-[22px]",
          side === "left" ? "rounded-l-xs bg-foreground" : "rounded-r-xs bg-brand",
        )}
        // The width comes from the data of the chart, so it cannot be a class.
        style={{ width: `${share}%` }}
      />
    </div>
  );
}

/**
 * Two players on shared metrics: one row for each metric, with the two values
 * as numbers and as bars. It goes inside the figure of ChartPanel. Each value
 * is always visible, so the chart has no interactive part.
 */
export function CompareBars({ chart }: { chart: CompareBarsSpec }) {
  const [first, second] = chart.series;
  const crossSeason = isCrossSeason(chart.series);

  return (
    <>
      <ChartTitle>{chart.title}</ChartTitle>
      <div className="@container">
        <div
          role="table"
          aria-label={`${first.player} (${first.season}) and ${second.player} (${second.season})`}
          className="flex flex-col"
        >
          <div role="row" className={cn(ROW, "items-end pb-5")}>
            <PlayerHeader series={first} side="left" />
            <span role="columnheader" className="sr-only">
              Metric
            </span>
            {/* The header of the metrics has no visible text, so its place is kept. */}
            <span aria-hidden="true" />
            <PlayerHeader series={second} side="right" />
          </div>
          {chart.metrics.map((metric) => {
            const [left, right] = metric.values;
            const rowMax = Math.max(left, right);
            return (
              <div
                key={metric.name}
                role="row"
                className={cn(ROW, "min-h-[52px] border-t border-line-subtle last:border-b")}
              >
                <div role="cell" className="flex items-center gap-2 @md:gap-4">
                  <span className={cn(VALUE, "text-right")}>{valueText(left)}</span>
                  <Bar share={barShare(left, rowMax)} side="left" />
                </div>
                <span role="rowheader" className="text-center text-sm font-semibold @md:text-base">
                  {metricLabel(metric.name)}
                  {crossSeason && isModelMetric(metric.name) && (
                    <>
                      {" "}
                      <span aria-hidden="true" className="text-caveat">
                        △
                      </span>
                      <span className="sr-only">different xG models</span>
                    </>
                  )}
                </span>
                <div role="cell" className="flex items-center gap-2 @md:gap-4">
                  <Bar share={barShare(right, rowMax)} side="right" />
                  <span className={cn(VALUE, "text-brand")}>{valueText(right)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Each row is scaled to its higher value.
        {hasModelCaveat(chart) && (
          <>
            {" "}
            <span aria-hidden="true" className="text-caveat">
              △
            </span>{" "}
            The two seasons use different xG models. Compare who is higher, not by how much.
          </>
        )}
      </p>
      <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
        <strong className="text-foreground">Chart summary.</strong> {summaryText(chart)}
      </figcaption>
    </>
  );
}
