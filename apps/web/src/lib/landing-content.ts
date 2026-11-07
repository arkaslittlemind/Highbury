// The copy of the landing page that also goes into /index.md, /llms.txt, and
// /llms-full.txt. One module, so the page and the Markdown cannot drift apart.
// Plain data only: a route handler imports it, and must not pull in a client
// component.

export const HERO = {
  // The component puts the second line in italic.
  headline: ["Two Arsenal eras.", "Every number checked."],
  intro:
    "An AI football analyst for the 2003-04 Invincibles and the 2025-26 side. It queries the data, draws the pitch chart, and checks every number before you see it.",
};

export type Capability = {
  title: string;
  text: string;
  // The question that the Try link puts into the hero bar.
  try: { label: string; question: string };
};

// The same question is the Try of two cards, as in the design.
const HENRY_V_SAKA = "Compare Henry in 2003-04 with Saka in 2025-26 on goals and xG per 90.";

export const HOW_IT_WORKS: {
  headline: [string, string];
  // The line under the headline on the page. It speaks of hover, so the
  // Markdown copies do not use it.
  hint: string;
  cards: Capability[];
} = {
  headline: ["See what it can do.", "Then ask your own."],
  hint: "Hover a card to watch the analyst work. Not sure where to start? Each card has a question you can try.",
  cards: [
    {
      title: "Ask in plain English",
      text: "No query language. It reads what each season holds before it writes a query, so it knows 2025-26 has no passes.",
      try: { label: "Henry vs Saka per 90", question: HENRY_V_SAKA },
    },
    {
      title: "Charts from the data",
      text: "Shot maps, heatmaps, pass networks and xG timelines. Every mark on the pitch is a row the analyst fetched.",
      try: {
        label: "Henry's shots v Liverpool",
        question: "Show Henry's shots in the 4-2 win over Liverpool in April 2004.",
      },
    },
    {
      title: "Compare the two eras",
      text: "Only the metrics both seasons hold, side by side, and it names the two xG models so the comparison stays fair.",
      try: { label: "Henry vs Saka", question: HENRY_V_SAKA },
    },
    {
      title: "Checks every number",
      text: "Plain code matches each number to the read-only query that produced it. A claim with no support is removed before you see it, and you can open the SQL.",
      try: {
        label: "Saka's minutes and goals per 90",
        question:
          "How many minutes did Bukayo Saka play in the 2025-26 league season, and how many goals did he score per 90 minutes?",
      },
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
