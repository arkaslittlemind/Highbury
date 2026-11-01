import { describe, expect, it } from "vitest";

import robots from "@/app/robots";
import { SITE_URL } from "@/lib/site";

const AI_SEARCH = [
  "OAI-SearchBot",
  "ChatGPT-User",
  "Claude-SearchBot",
  "Claude-User",
  "PerplexityBot",
  "Perplexity-User",
];
const AI_TRAINING = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot"];

function rules() {
  const { rules } = robots();
  return Array.isArray(rules) ? rules : [rules];
}

// The rule whose user agents include this one.
function ruleFor(agent: string) {
  return rules().find((rule) => [rule.userAgent].flat().includes(agent));
}

describe("robots", () => {
  it("allows the AI search crawlers and the fetches a person asks for", () => {
    for (const agent of AI_SEARCH) {
      expect(ruleFor(agent)).toMatchObject({ allow: "/" });
      expect(ruleFor(agent)?.disallow).toBeUndefined();
    }
  });

  it("blocks the AI training crawlers", () => {
    for (const agent of AI_TRAINING) expect(ruleFor(agent)).toMatchObject({ disallow: "/" });
  });

  it("allows every other crawler, and names the sitemap", () => {
    expect(ruleFor("*")).toMatchObject({ allow: "/" });
    expect(robots().sitemap).toBe(`${SITE_URL}/sitemap.xml`);
  });
});
