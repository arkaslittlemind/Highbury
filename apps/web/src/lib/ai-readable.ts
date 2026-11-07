import { DATA_SOURCES, HERO, HOW_IT_WORKS, NOTICE, SEASONS, type Season } from "@/lib/landing-content";
import { SITE_DESCRIPTION, SITE_URL } from "@/lib/site";

// The text that AI agents read in place of the page: /index.md, /llms.txt, and
// /llms-full.txt. Each fact comes from the copy of the page or from site.ts,
// so the Markdown says only what the page says.

const HOME_URL = `${SITE_URL}/`;

function seasonSection(season: Season): string {
  const lines = [
    `### ${season.label} (${season.source})`,
    "",
    season.line,
    "",
    ...season.has.map((item) => `- ${item}`),
  ];
  lines.push("", `**${season.note.lead}** ${season.note.text}`);
  return lines.join("\n");
}

export function renderHomeMarkdown(): string {
  return [
    "# Highbury",
    "",
    `> ${SITE_DESCRIPTION}`,
    "",
    `Canonical: ${HOME_URL}`,
    "",
    `## ${HERO.headline.join(" ")}`,
    "",
    HERO.intro,
    "",
    `## How it works: ${HOW_IT_WORKS.headline.join(" ")}`,
    "",
    ...HOW_IT_WORKS.cards.map(
      (card, index) => `${index + 1}. **${card.title}.** ${card.text} Try: "${card.try.question}"`,
    ),
    "",
    `## Seasons: ${SEASONS.headline.join(" ")}`,
    "",
    SEASONS.lead,
    "",
    seasonSection(SEASONS.then),
    "",
    seasonSection(SEASONS.now),
    "",
    SEASONS.note,
    "",
    "## How to use it",
    "",
    `Open [Highbury](${HOME_URL}) and ask a question in plain English. Every answer shows the tools it called, the SQL it ran, and which numbers passed the check.`,
    "",
    "## About",
    "",
    NOTICE,
    "",
    `Data: ${DATA_SOURCES.join(", ")}.`,
    "",
    "## Related",
    "",
    `- [Highbury](${HOME_URL}): the analyst, in the browser`,
    `- [llms.txt](${SITE_URL}/llms.txt): a short guide to this site for AI agents`,
    "",
  ].join("\n");
}

export function renderLlmsTxt(): string {
  return [
    "# Highbury",
    "",
    `> ${SITE_DESCRIPTION}`,
    "",
    `Highbury covers two Arsenal seasons: 2003-04 (${SEASONS.then.source}) and 2025-26 (${SEASONS.now.source}). It queries the data read-only and checks every number before you see it. When the data cannot answer, it says so. It is free to use and an unofficial fan project. Data: ${DATA_SOURCES.join(", ")}.`,
    "",
    "## Core pages",
    "",
    `- [Home](${SITE_URL}/index.md): what Highbury is, how it checks answers, and what each season holds`,
    "",
    "## Machine-readable",
    "",
    `- [Full content](${SITE_URL}/llms-full.txt): every page of this site in one text`,
    `- [Sitemap](${SITE_URL}/sitemap.xml): the HTML pages`,
    "",
  ].join("\n");
}

export function renderLlmsFullTxt(): string {
  return [
    "# Highbury - full content",
    "",
    `> ${SITE_DESCRIPTION}`,
    "",
    "---",
    `<!-- source: ${HOME_URL} -->`,
    "",
    renderHomeMarkdown(),
  ].join("\n");
}
