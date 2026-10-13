import { ChartTitle } from "@/components/charts/chart-title";
import { CompareBars } from "@/components/charts/compare-bars";
import { ShotMap } from "@/components/charts/shot-map";
import type { ChartSpec } from "@/lib/analyst-schema";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function countsText(chart: Extract<ChartSpec, { type: "pass_network" }>): string {
  return `${plural(chart.nodes.length, "player", "players")}, ${plural(chart.edges.length, "passing link", "passing links")}`;
}

/**
 * The place of one chart of an answer. A shot map and a comparison are drawn. The
 * drawing of the pass network comes with a later feature. Null means that no valid chart
 * came for the id.
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
      ) : (
        <>
          <ChartTitle>{chart.title}</ChartTitle>
          <figcaption className="border-t pt-3.5 text-[15px] text-foreground-2">
            {countsText(chart)}
          </figcaption>
        </>
      )}
    </figure>
  );
}
