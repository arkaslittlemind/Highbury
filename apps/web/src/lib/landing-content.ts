// The copy of the landing page that also goes into /index.md, /llms.txt, and
// /llms-full.txt. One module, so the page and the Markdown cannot drift apart.
// Plain data only: a route handler imports it, and must not pull in a client
// component.

export const HERO = {
  // The component puts the second line in italic.
  headline: ["Two Arsenal eras.", "Every number checked."],
  intro:
    "An AI football analyst for Arsenal's 2003-04 Invincibles and the 2025-26 side. Ask in plain English: Highbury queries the data, draws the pitch chart, and checks every number before you see it. When the data cannot answer, it says so.",
};

export const HOW_IT_WORKS = {
  headline: ["Not a chatbot.", "An analyst with receipts."],
  lead: "Every answer shows the tools it called, the SQL it ran, and which numbers passed the check.",
  cards: [
    {
      title: "Reads the catalog first",
      text: "The agent reads what each season holds before it writes a query, so it knows that 2025-26 has shots but no passes.",
    },
    {
      title: "Queries read-only",
      text: "One SELECT in each call, checked by a parser and run as a read-only role with a 5-second timeout and a row limit.",
    },
    {
      title: "Checks every number",
      text: "Plain code checks every number against the tool output that it cites. A claim with no support is removed before you see it.",
    },
  ],
};

export type Season = {
  label: string;
  source: string;
  line: string;
  // What the season holds. The data catalog of the service is the source.
  has: string[];
  lacks?: string;
};

export const SEASONS: {
  headline: [string, string];
  then: Season;
  now: Season;
  note: string;
} = {
  headline: ["Two seasons.", "Honest about the gaps."],
  then: {
    label: "2003-04",
    source: "StatsBomb Open Data",
    line: "The Invincibles · 26 W 12 D 0 L",
    has: [
      "Shots with StatsBomb xG and coordinates",
      "Passes and pressures, with coordinates",
      "Player stats for each match and for the season",
      "Every league match and the table, from football-data.co.uk",
    ],
  },
  now: {
    label: "2025-26",
    source: "Understat",
    line: "The current side, shot by shot",
    has: [
      "Shots with Understat xG and coordinates",
      "Player stats for each match and for the season",
      "Every league match and the table, from football-data.co.uk",
      "FPL points, saves, clean sheets, and bonus for each match",
    ],
    lacks: "No pass data. Highbury says so and offers a shot map.",
  },
  note: "A comparison of the two seasons uses only the metrics that both have, and says that the two xG models are different.",
};

// The footer lines of the page.
export const NOTICE =
  "Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the Premier League.";
export const DATA_SOURCES = ["StatsBomb Open Data", "Understat", "football-data.co.uk", "FPL"];
