import type { ShotMapSpec } from "@/lib/shot-map";

const MATCH = {
  opponent: "Liverpool",
  player: "Thierry Henry",
  season: "2003-04",
  match_date: "2004-04-09",
};

/**
 * The chart of the landing screen: the nine shots of Thierry Henry in the 4-2
 * win against Liverpool. It is a copy of the rows of v_shots (StatsBomb Open
 * Data), so the page can show a real chart before a visitor asks. It does not
 * change when the database changes.
 */
export const SAMPLE_SHOT_MAP: ShotMapSpec = {
  type: "shot_map",
  id: "sample",
  title: "Henry v Liverpool, 9 April 2004",
  shots: [
    { ...MATCH, minute: 26, x: 103.1, y: 28.1, xg: 0.03, outcome: "off target" },
    { ...MATCH, minute: 30, x: 104.3, y: 30.3, xg: 0.31, outcome: "goal" },
    { ...MATCH, minute: 32, x: 91.3, y: 26.1, xg: 0.02, outcome: "blocked" },
    { ...MATCH, minute: 45, x: 118.3, y: 47.4, xg: 0.13, outcome: "off target" },
    { ...MATCH, minute: 49, x: 112.1, y: 30.0, xg: 0.3, outcome: "goal" },
    { ...MATCH, minute: 55, x: 89.5, y: 28.7, xg: 0.02, outcome: "off target" },
    { ...MATCH, minute: 68, x: 111.4, y: 39.2, xg: 0.11, outcome: "off target" },
    { ...MATCH, minute: 76, x: 112.9, y: 42.7, xg: 0.24, outcome: "goal" },
    { ...MATCH, minute: 76, x: 111.6, y: 41.2, xg: 0.27, outcome: "saved" },
  ],
};
