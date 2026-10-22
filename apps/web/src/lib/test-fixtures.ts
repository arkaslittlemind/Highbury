// Payloads in the form that the analyst service sends them. Only tests use this file.

export const SHOT = {
  x: 108.2,
  y: 41.5,
  xg: 0.52,
  outcome: "goal",
  minute: 39,
  opponent: "Liverpool",
  player: "Thierry Henry",
  season: "2003-04",
  match_date: "2004-04-09",
};

export const SHOT_MAP = {
  type: "shot_map",
  id: "chart_1",
  title: "Thierry Henry, shots in 2003-04",
  shots: [SHOT, { ...SHOT, x: 96, xg: 0.18, outcome: "saved", minute: 12, player: null }],
};

export const COMPARE_BARS = {
  type: "compare_bars",
  id: "chart_2",
  title: "Henry 2003-04 and Saka 2025-26",
  series: [
    { player: "Thierry Henry", season: "2003-04" },
    { player: "Bukayo Saka", season: "2025-26" },
  ],
  metrics: [
    { name: "goals", values: [30, 16] },
    { name: "xg_per_90", values: [0.61, 0.38] },
  ],
};

export const PASS_NETWORK = {
  type: "pass_network",
  id: "chart_3",
  title: "Arsenal passes against Liverpool",
  nodes: [
    { player: "Patrick Vieira", x: 60, y: 40, passes: 48 },
    { player: "Robert Pires", x: 78.5, y: 18, passes: 31 },
  ],
  edges: [{ source: "Patrick Vieira", target: "Robert Pires", passes: 9 }],
};

export const XG_TIMELINE = {
  type: "xg_timeline",
  id: "chart_4",
  title: "Arsenal v Liverpool, xG by minute",
  teams: [
    {
      team: "Arsenal",
      xg: 1.33,
      shots: [
        { minute: 9, xg: 0.13, total: 0.13, is_goal: false, player: "Robert Pires" },
        { minute: 31, xg: 0.42, total: 0.55, is_goal: true, player: "Thierry Henry" },
        { minute: 49, xg: 0.78, total: 1.33, is_goal: true, player: null },
      ],
    },
    {
      team: "Liverpool",
      xg: 0.07,
      shots: [{ minute: 31, xg: 0.07, total: 0.07, is_goal: false, player: "Steven Gerrard" }],
    },
  ],
};

export const STEP = { number: 1, tool: "run_sql", label: "Querying the match data" };

const CLAIM = { text: "Goals", value: 30, unit: "goals", tool_call_id: "q_1a2b3c4d" };

export const ANSWER_DATA = {
  conversation_id: "0123456789abcdef0123456789abcdef",
  cached: false,
  answer: {
    status: "answered",
    summary: "Henry scored 30 goals from 3.1 shots per 90.",
    claims: [CLAIM],
    charts: [{ id: "chart_1" }],
    caveats: ["xG here is the model of StatsBomb."],
    alternative: null,
  },
  verification: {
    checked: 2,
    passed: 1,
    removed: [
      {
        claim: { text: "Shots per 90", value: 3.4, unit: "", tool_call_id: "q_ffffffff" },
        reason: "value_not_found",
      },
    ],
    unbacked_numbers: ["3.1"],
  },
  working: [
    {
      tool: "resolve_player",
      args: { name: "Henry" },
      sql: null,
      row_count: null,
      error: null,
      call_id: null,
    },
    {
      tool: "run_sql",
      args: { sql: "SELECT goals FROM v_player_season" },
      sql: "SELECT goals FROM v_player_season LIMIT 200",
      row_count: 1,
      error: null,
      call_id: "q_1a2b3c4d",
    },
  ],
};

/** One server-sent event as the service writes it. */
export function sse(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}
