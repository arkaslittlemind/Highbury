import { CompareBars } from "@/components/charts/compare-bars";
import { PassNetwork } from "@/components/charts/pass-network";
import { PointsPace } from "@/components/charts/points-pace";
import { ShotMap } from "@/components/charts/shot-map";
import { XgTimeline } from "@/components/charts/xg-timeline";
import type { ChartSpec } from "@/lib/analyst-schema";

/**
 * The place of one chart of an answer. Null means that no valid chart came for the id.
 */
export function ChartPanel({ chart }: { chart: ChartSpec | null }) {
  if (!chart) {
    return (
      <figure className="flex flex-col gap-2 rounded-panel border border-caveat-line bg-caveat-bg p-6">
        <strong className="text-caveat-strong">This chart cannot be shown</strong>
        <figcaption className="text-caveat-text">
          Its data did not pass the check of the page. The answer and its numbers are as
          the analyst gave them.
        </figcaption>
      </figure>
    );
  }
  return (
    <figure className="flex flex-col gap-4 rounded-panel border bg-surface-chart p-6">
      {chart.type === "shot_map" ? (
        <ShotMap chart={chart} />
      ) : chart.type === "compare_bars" ? (
        <CompareBars chart={chart} />
      ) : chart.type === "pass_network" ? (
        <PassNetwork chart={chart} />
      ) : chart.type === "xg_timeline" ? (
        <XgTimeline chart={chart} />
      ) : (
        <PointsPace chart={chart} />
      )}
    </figure>
  );
}
