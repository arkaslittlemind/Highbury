import raw from "@/lib/landing-data.json";
import type { ChartSpec } from "@/lib/analyst-schema";

// The data of the landing page. `python -m analyst.landing_data` writes the JSON from
// the database and the eval runs; the page reads no database. landing-data.test.ts
// checks each chart against the schema of an answer.

export type GalleryTile = {
  // The id of the golden question that the tile shows. Its Try link asks it.
  id: string;
  question: string;
  // The short text of the Try link.
  label: string;
  // The seasons that have this chart type.
  season: string;
  chart: ChartSpec;
};

export type SeasonRecord = { won: number; drawn: number; lost: number };

export type Proof = {
  model: string;
  // YYYY-MM-DD of the newest eval run of the production model.
  runDate: string;
  correct: number;
  correctTotal: number;
  verifiedRate: number | null;
  chartMatches: number;
  chartTotal: number;
  refusals: number;
  refusalTotal: number;
};

type LandingData = {
  tiles: GalleryTile[];
  records: Record<"2003-04" | "2025-26", SeasonRecord>;
  capabilities: { sakaMinutes: number; sakaGoalsPer90: number; henryGoalsPer90: number };
  proof: Proof;
};

// A JSON import has wide types (a string, not "shot_map"). The test parses it.
export const LANDING_DATA = raw as unknown as LandingData;

/** The compare bars of the gallery: Henry 2003-04 and Saka 2025-26. Capability card 3 uses it. */
export function compareTile(data: LandingData = LANDING_DATA) {
  const chart = data.tiles.find((tile) => tile.chart.type === "compare_bars")?.chart;
  if (chart?.type !== "compare_bars") throw new Error("The landing data has no compare bars.");
  return chart;
}
