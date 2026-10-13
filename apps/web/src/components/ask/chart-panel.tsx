import { ChartTitle } from "@/components/charts/chart-title";
import { ShotMap } from "@/components/charts/shot-map";
import type { ChartSpec } from "@/lib/analyst-schema";

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function countsText(chart: Exclude<ChartSpec, { type: "shot_map" }>): string {
  switch (chart.type) {
    case "compare_bars": {
      const [first, second] = chart.series;
      return `${first.player} (${first.season}) and ${second.player} (${second.season}), ${plural(chart.metrics.length, "metric", "metrics")}`;
    }
    case "pass_network":
      return `${plural(chart.nodes.length, "player", "players")}, ${plural(chart.edges.length, "passing link", "passing links")}`;
  }
}

/**
 * The place of one chart of an answer. A shot map is drawn. The drawing of the
 * other chart types comes with a later feature. Null means that no valid chart
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
