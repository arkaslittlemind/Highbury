import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// The contrast check of the page: WCAG 2.1 level AA for the colour pairs that
// the page uses. The values come from globals.css, so a change of a token
// that makes a text hard to read fails here.

const css = readFileSync(fileURLToPath(new URL("./globals.css", import.meta.url)), "utf8");
const root = css.slice(css.indexOf(":root {"));

/** The hex value of a token. A token can point at one other token. */
function token(name: string): string {
  const value = new RegExp(`--${name}:\\s*([^;]+);`).exec(root)?.[1].trim();
  if (!value) throw new Error(`No token --${name} in globals.css`);
  const pointer = /^var\(--([a-z0-9-]+)\)$/.exec(value);
  return pointer ? token(pointer[1]) : value;
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
  const [red, green, blue] = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrast(first: string, second: string): number {
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

const TEXT = 4.5;
// Large text, marks, and indicators.
const MARK = 3;

const SURFACES = ["background", "card", "surface-chart"];

const PAIRS: [foreground: string, backgrounds: string[], minimum: number][] = [
  ["foreground", SURFACES, TEXT],
  ["foreground-2", SURFACES, TEXT],
  ["muted-foreground", [...SURFACES, "surface-sunken"], TEXT],
  // Placeholder text, and the row numbers of the working.
  ["faint", ["background", "surface-sunken"], TEXT],
  ["brand", SURFACES, TEXT],
  ["brand-soft", ["card"], TEXT],
  ["primary-foreground", ["primary"], TEXT],
  ["verified", ["verified-bg", "card"], TEXT],
  ["verified-strong", ["verified-bg-2"], MARK],
  ["caveat-strong", ["caveat-bg"], TEXT],
  ["caveat-text", ["caveat-bg"], TEXT],
  ["caveat", ["surface-chart", "card", "caveat-bg"], MARK],
  ["info", ["card"], TEXT],
  ["info-icon", ["card"], MARK],
  ["code", ["code-bg"], TEXT],
  // The tooltip of a shot is light, with dark text.
  ["tooltip-muted", ["foreground"], TEXT],
  ["ring", SURFACES, MARK],
  // The landing screen. The light cards have dark text.
  ["background", ["paper"], TEXT],
  ["paper-muted", ["paper"], TEXT],
  ["verified-on-paper", ["paper"], TEXT],
  // Text on the grass. grass-600 is the lightest grass below body text: the
  // shade of the hero makes it darker than this on the page.
  ["foreground", ["grass-800", "grass-700", "grass-600"], TEXT],
  ["on-grass", ["grass-800", "grass-700", "grass-600"], TEXT],
  ["on-grass-muted", ["grass-800"], TEXT],
  // The headline of the last panel goes down to the lightest grass.
  ["foreground", ["grass-500"], MARK],
  // The ring of a light pill is 3px outside it, on the grass. Nothing on a
  // light card takes the focus.
  ["ring", ["grass-800", "grass-500"], MARK],
  // The card of 2025-26.
  ["brand-soft", ["now-900"], TEXT],
  ["now-text", ["now-900"], TEXT],
  ["now-muted", ["now-900", "now-950"], TEXT],
  ["verified", ["now-900", "grass-700"], TEXT],
];

describe("contrast", () => {
  it("is 21 for white on black", () => {
    expect(contrast("#FFFFFF", "#000000")).toBeCloseTo(21);
  });

  it("is the same in the two directions", () => {
    expect(contrast("#0A120E", "#F1EEE6")).toBe(contrast("#F1EEE6", "#0A120E"));
  });
});

describe("the colour tokens", () => {
  for (const [foreground, backgrounds, minimum] of PAIRS) {
    for (const background of backgrounds) {
      it(`${foreground} on ${background} has a contrast of ${minimum} or more`, () => {
        expect(contrast(token(foreground), token(background))).toBeGreaterThanOrEqual(minimum);
      });
    }
  }
});
