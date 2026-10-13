import type { ChartSpec } from "@/lib/analyst-schema";

export type CompareBarsSpec = Extract<ChartSpec, { type: "compare_bars" }>;
export type Series = CompareBarsSpec["series"][number];

// The words of a metric name that are a number of an xG model, with their spelling.
const MODEL_WORDS = new Map([
  ["xg", "xG"],
  ["xa", "xA"],
  ["npxg", "npxG"],
]);

/** The label of a metric. Its name is a column of the query, for example xg_per_90. */
export function metricLabel(name: string): string {
  const label = name
    .replaceAll("_", " ")
    .split(" ")
    .map((word) => MODEL_WORDS.get(word.toLowerCase()) ?? word)
    .join(" ");
  const first = label.split(" ")[0];
  // A capital X in xG is wrong.
  if (MODEL_WORDS.has(first.toLowerCase())) return label;
  return label.charAt(0).toUpperCase() + label.slice(1);
}

const valueFormat = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 });

/** A value as the chart shows it. The chart calculates no new number. */
export function valueText(value: number): string {
  return valueFormat.format(value);
}

/**
 * The width of a bar, as a percentage of its cell. Each row has its own scale:
 * rowMax is the higher value of the row, so that value has the full width.
 */
export function barShare(value: number, rowMax: number): number {
  if (rowMax <= 0 || value <= 0) return 0;
  return (value / rowMax) * 100;
}

/** True for a metric that comes from an xG model, which differs between the seasons. */
export function isModelMetric(name: string): boolean {
  return name.split(/[^a-z0-9]+/i).some((word) => MODEL_WORDS.has(word.toLowerCase()));
}

export function isCrossSeason(series: Series[]): boolean {
  return series[0].season !== series[1].season;
}

/** True for a chart that has a row with the mark of the model caveat. */
export function hasModelCaveat(chart: CompareBarsSpec): boolean {
  return isCrossSeason(chart.series) && chart.metrics.some((metric) => isModelMetric(metric.name));
}

/**
 * The chart in words, one sentence for each metric. It says "is higher" and
 * not "leads", because for some metrics a lower value is better.
 */
export function summaryText(chart: CompareBarsSpec): string {
  const sentences = chart.metrics.map((metric) => {
    const label = metricLabel(metric.name);
    const [first, second] = metric.values;
    if (first === second) return `${label}: level at ${valueText(first)}.`;
    const higher = chart.series[first > second ? 0 : 1];
    const pair = `${valueText(Math.max(first, second))} to ${valueText(Math.min(first, second))}`;
    return `${label}: ${higher.player} (${higher.season}) is higher, ${pair}.`;
  });
  if (hasModelCaveat(chart)) sentences.push("The two seasons use different xG models.");
  return sentences.join(" ");
}
