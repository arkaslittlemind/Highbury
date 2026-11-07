import { describe, expect, it } from "vitest";

import { renderHomeMarkdown, renderLlmsFullTxt, renderLlmsTxt } from "@/lib/ai-readable";
import { HOW_IT_WORKS, NOTICE, SEASONS } from "@/lib/landing-content";
import { SITE_DESCRIPTION, SITE_URL } from "@/lib/site";

// Every URL of a Markdown link, for example [Home](https://...).
function links(markdown: string): string[] {
  return [...markdown.matchAll(/\]\(([^)]+)\)/g)].map((match) => match[1]);
}

describe("renderHomeMarkdown", () => {
  const markdown = renderHomeMarkdown();

  it("starts with the title, the summary, and the canonical URL", () => {
    const [title, , summary, , canonical] = markdown.split("\n");
    expect(title).toBe("# Highbury");
    expect(summary).toBe(`> ${SITE_DESCRIPTION}`);
    expect(canonical).toBe(`Canonical: ${SITE_URL}/`);
  });

  it("holds the facts of the page", () => {
    expect(markdown).toContain(NOTICE);
    for (const card of HOW_IT_WORKS.cards) {
      expect(markdown).toContain(card.title);
      expect(markdown).toContain(card.try.question);
    }
    expect(markdown).toContain(SEASONS.then.label);
    expect(markdown).toContain(SEASONS.now.label);
    expect(markdown).toContain(SEASONS.now.note.text);
    expect(markdown).toContain(SEASONS.then.note.lead);
    expect(markdown).toContain(SEASONS.note);
  });

  it("links only absolute HTML URLs on the site", () => {
    const urls = links(markdown);
    expect(urls.length).toBeGreaterThan(0);
    for (const url of urls) {
      expect(url.startsWith(`${SITE_URL}/`)).toBe(true);
      expect(url.endsWith(".md")).toBe(false);
    }
  });
});

describe("renderLlmsTxt", () => {
  const text = renderLlmsTxt();

  // The summary is the site description itself, so it cannot drift from the page.
  it("starts with the name and the site description", () => {
    expect(text.split("\n").slice(0, 3)).toEqual(["# Highbury", "", `> ${SITE_DESCRIPTION}`]);
  });

  it("links the Markdown page and the full text, all absolute", () => {
    const urls = links(text);
    expect(urls).toContain(`${SITE_URL}/index.md`);
    expect(urls).toContain(`${SITE_URL}/llms-full.txt`);
    for (const url of urls) expect(url.startsWith(`${SITE_URL}/`)).toBe(true);
  });
});

describe("renderLlmsFullTxt", () => {
  it("holds the home Markdown under its source", () => {
    const text = renderLlmsFullTxt();
    expect(text.startsWith("# Highbury - full content\n")).toBe(true);
    expect(text).toContain(`---\n<!-- source: ${SITE_URL}/ -->\n\n${renderHomeMarkdown()}`);
  });
});
