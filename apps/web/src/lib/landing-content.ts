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
  label: "2003-04" | "2025-26";
  source: string;
  line: string;
  // What the season holds. The data catalog of the service is the source.
  has: string[];
  // The box under the list: what is special about the season's data. The lead is bold.
  note: { lead: string; text: string };
};

export const SEASONS: {
  headline: [string, string];
  lead: string;
  then: Season;
  now: Season;
  note: string;
} = {
  headline: ["Two seasons.", "Honest about the gaps."],
  lead: "What each season holds, and what it does not. The analyst reads this before every query.",
  then: {
    label: "2003-04",
    source: "StatsBomb Open Data",
    line: "The Invincibles",
    has: [
      "Shots with StatsBomb xG and coordinates",
      "Passes and pressures, with coordinates",
      "Player stats for each match and for the season",
      "Every league match and the table",
    ],
    note: { lead: "All 38 league matches", text: "of Arsenal, event by event." },
  },
  now: {
    label: "2025-26",
    source: "Understat · FPL",
    line: "The 2025-26 side, shot by shot",
    has: [
      "Shots with Understat xG and coordinates",
      "Player stats for each match and for the season",
      "Every league match and the table",
      "FPL points, saves, clean sheets and bonus",
    ],
    note: {
      lead: "No pass data.",
      text: "Understat records shots only. Highbury says so and offers a shot map.",
    },
  },
  note: "A comparison of the two seasons uses only the metrics both hold, and names the two xG models: StatsBomb for 2003-04, Understat for 2025-26.",
};

// The footer lines of the page.
export const NOTICE =
  "Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the Premier League.";
export const DATA_SOURCES = ["StatsBomb Open Data", "Understat", "football-data.co.uk", "FPL"];

export type FaqItem = {
  question: string;
  // One string for each paragraph of the answer.
  answer: string[];
};

export const FAQ: {
  headline: string;
  lead: string;
  groups: { title: string; items: FaqItem[] }[];
} = {
  headline: "Questions, answered.",
  lead: "What Highbury can do, what it cannot, and why.",
  groups: [
    {
      title: "Asking questions",
      items: [
        {
          question: "What can I ask?",
          answer: [
            "Anything about Arsenal's 2003-04 and 2025-26 league seasons: shots and xG, goals, passes and heatmaps for 2003-04, results and the table, FPL points for 2025-26, and comparisons between players and between the two eras.",
          ],
        },
        {
          question: "Do I need to know football stats or SQL?",
          answer: [
            "No. Ask in plain English and the analyst writes the query. If you are not sure where to start, each card above has a question you can try with one click.",
          ],
        },
        {
          question: "Can I ask a follow-up question?",
          answer: [
            'Yes. Ask in the same conversation, for example "Now show his whole season", and the analyst keeps the context of the answer before.',
          ],
        },
        {
          question: "How many questions can I ask?",
          answer: [
            "Up to 10 a day. Highbury is free, and every answer costs money to run, so each visitor has a daily allowance. It resets at midnight UTC.",
          ],
        },
      ],
    },
    {
      title: "The data",
      items: [
        {
          question: "Which matches does it cover?",
          answer: [
            "2003-04: Arsenal's 38 league matches, from StatsBomb Open Data. 2025-26: Arsenal's shots with Understat xG, and the FPL numbers of every Premier League player.",
            "For both seasons it also has every league result and the table, from football-data.co.uk.",
          ],
        },
        {
          question: "Why can't it show passes for 2025-26?",
          answer: [
            "Understat records shots, not passes. Highbury says so instead of guessing, and offers a shot map.",
          ],
        },
        {
          question: "Why is xG different between the two seasons?",
          answer: [
            "The seasons come from two xG models: StatsBomb for 2003-04 and Understat for 2025-26. Every comparison names both, so you know the numbers are close but not identical in method.",
          ],
        },
        {
          question: "Can it answer about other seasons or other clubs?",
          answer: [
            "Not other seasons. Other clubs only through the league table, the results, and the 2025-26 FPL numbers. When a question is out of scope, it tells you.",
          ],
        },
      ],
    },
    {
      title: "Trust and privacy",
      items: [
        {
          question: "How do I know a number is right?",
          answer: [
            'Plain code checks every number in an answer against the read-only query that produced it. A claim with no support is removed before you see it. Open "Show the working" to see each query and its rows.',
          ],
        },
        {
          question: "Can it still be wrong?",
          answer: [
            "Yes. It can misread a question or choose a different measure than you meant. The check proves that each number matches the data, not that it understood you, so read the working when it matters.",
          ],
        },
        {
          question: "What happens to my question?",
          answer: [
            "Your question goes to the AI model provider, currently Google Gemini, to write the answer. Highbury's own logs record counts and cost for each question, never its text.",
          ],
        },
        {
          question: "Is this an official Arsenal product?",
          answer: [
            "No. Highbury is an unofficial fan project, not affiliated with or endorsed by Arsenal FC or the Premier League.",
          ],
        },
      ],
    },
  ],
};
