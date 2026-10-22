import { scaleLinear, scaleSqrt } from "d3-scale";

import type { ChartSpec } from "@/lib/analyst-schema";
import { toPitchPoint, tooltipPlaceAt, type TooltipPlace } from "@/lib/pitch";

export type PassNetworkSpec = Extract<ChartSpec, { type: "pass_network" }>;
export type PassNode = PassNetworkSpec["nodes"][number];

/** The line between two players, with the passes in each direction. a sorts before b. */
export type Link = { a: string; b: string; aToB: number; bToA: number; passes: number };

/** A player at the other end of the links of one player, with the passes each way. */
export type Partner = { player: string; to: number; from: number; passes: number };

// The number of partners that a label and a tooltip name.
const TOP_PARTNERS = 3;
// The links with fewer passes are noise for the shape of the team, so they start hidden.
const DEFAULT_MIN_PASSES = 3;

/**
 * One link for each pair of players. Two directed lines that lie on top of each
 * other cannot be read, so the line is for the pair and the counts keep the
 * directions. The schema does not check that an edge ends at a node, so an edge
 * that does not, or that goes from a player to themself, is left out.
 */
export function links(spec: PassNetworkSpec): Link[] {
  const players = new Set(spec.nodes.map((node) => node.player));
  const byPair = new Map<string, Link>();
  for (const edge of spec.edges) {
    const { source, target } = edge;
    if (source === target || !players.has(source) || !players.has(target)) continue;
    const [a, b] = source < target ? [source, target] : [target, source];
    const key = JSON.stringify([a, b]);
    const link = byPair.get(key) ?? { a, b, aToB: 0, bToA: 0, passes: 0 };
    if (source === a) link.aToB += edge.passes;
    else link.bToA += edge.passes;
    link.passes += edge.passes;
    byPair.set(key, link);
  }
  return [...byPair.values()].sort(
    (first, second) =>
      second.passes - first.passes || first.a.localeCompare(second.a) || first.b.localeCompare(second.b),
  );
}

/** The first minimum of passes per link. It never hides every link of a network. */
export function defaultMinPasses(allLinks: Link[]): number {
  const most = Math.max(1, ...allLinks.map((link) => link.passes));
  return Math.min(DEFAULT_MIN_PASSES, most);
}

/**
 * The links that are drawn, in the order of links(): those with at least minPasses,
 * both directions together. The data table lists the same links.
 */
export function visibleLinks(allLinks: Link[], minPasses: number): Link[] {
  return allLinks.filter((link) => link.passes >= minPasses);
}

/** Which passes the network holds. The minute comes from the spec, never from the page. */
export function windowText(spec: PassNetworkSpec): string {
  return spec.until_minute == null
    ? "Whole match"
    : `Passes before the first substitution, ${spec.until_minute}'`;
}

/** The players from the most passes to the fewest. The keyboard and the drawing use this order. */
export function nodeOrder(nodes: PassNode[]): PassNode[] {
  return [...nodes].sort(
    (first, second) => second.passes - first.passes || first.player.localeCompare(second.player),
  );
}

/** The radius of a node in pitch units. The area grows with the passes. */
export function nodeRadius(passes: number, maxPasses: number): number {
  return scaleSqrt().domain([0, maxPasses]).range([1.5, 4.5]).clamp(true)(passes);
}

/** The width in pixels and the opacity of a link line. */
export function linkStyle(passes: number, maxPasses: number): { width: number; opacity: number } {
  const share = scaleLinear().domain([1, Math.max(maxPasses, 2)]).range([0, 1]).clamp(true)(passes);
  return { width: 1 + 5 * share, opacity: 0.25 + 0.65 * share };
}

/** The name on the pitch: the last word of the full name. */
export function shortName(player: string): string {
  return player.trim().split(/\s+/).at(-1) ?? player;
}

export type LabelSide = "below" | "above";

// The size of a name on the pitch, in pitch units: about 10 px at 390 px wide.
export const LABEL_SIZE = 2.8;
// The width of one character as a share of the size: a safe guess for the body font.
const CHAR_WIDTH = 0.6;
const LABEL_GAP = 0.6;

type Box = { left: number; right: number; top: number; bottom: number };

/** The baseline of a name below or above a node, from the centre of the node. */
export function labelOffset(side: LabelSide, radius: number): number {
  return side === "below" ? radius + LABEL_SIZE : -(radius + LABEL_GAP);
}

function labelBox(node: PassNode, side: LabelSide, radius: number): Box {
  const point = toPitchPoint(node.x, node.y);
  const half = (shortName(node.player).length * LABEL_SIZE * CHAR_WIDTH) / 2;
  const baseline = point.y + labelOffset(side, radius);
  // The text is mostly above its baseline.
  return {
    left: point.x - half,
    right: point.x + half,
    top: baseline - LABEL_SIZE * 0.8,
    bottom: baseline + LABEL_SIZE * 0.2,
  };
}

function overlaps(first: Box, second: Box): boolean {
  return (
    first.left < second.right &&
    second.left < first.right &&
    first.top < second.bottom &&
    second.top < first.bottom
  );
}

/**
 * Where the name of each node goes. Players who stand close together would have
 * names on top of each other, so a name goes below its node, else above it, else it
 * is left off. The players with the most passes choose first. A player with no name
 * on the pitch is still named by the label and the tooltip of the node.
 */
export function labelSides(nodes: PassNode[], maxPasses: number): Map<string, LabelSide> {
  const sides = new Map<string, LabelSide>();
  const placed: Box[] = [];
  for (const node of nodeOrder(nodes)) {
    const radius = nodeRadius(node.passes, maxPasses);
    for (const side of ["below", "above"] as const) {
      const box = labelBox(node, side, radius);
      if (placed.some((other) => overlaps(box, other))) continue;
      placed.push(box);
      sides.set(node.player, side);
      break;
    }
  }
  return sides;
}

/** The players that one player has links with, from the most passes to the fewest. */
export function partners(player: string, allLinks: Link[]): Partner[] {
  return allLinks
    .filter((link) => link.a === player || link.b === player)
    .map((link) =>
      link.a === player
        ? { player: link.b, to: link.aToB, from: link.bToA, passes: link.passes }
        : { player: link.a, to: link.bToA, from: link.aToB, passes: link.passes },
    );
}

function passesText(count: number): string {
  return `${count} ${count === 1 ? "pass" : "passes"}`;
}

/** The accessible name of a node. */
export function nodeLabel(node: PassNode, allLinks: Link[]): string {
  const made = `${node.player}, ${passesText(node.passes)} made.`;
  const top = partners(node.player, allLinks).slice(0, TOP_PARTNERS);
  if (top.length === 0) return made;
  const names = top.map((partner) => `${partner.player}, ${partner.to} to and ${partner.from} from`);
  return `${made} Top links: ${names.join("; ")}.`;
}

/** The lines of the tooltip of a node. The first one is the heading. */
export function tooltipLines(node: PassNode, allLinks: Link[]): string[] {
  const top = partners(node.player, allLinks).slice(0, TOP_PARTNERS);
  return [
    node.player,
    `${passesText(node.passes)} made`,
    ...top.map((partner) => `${shortName(partner.player)} · ${partner.to} to, ${partner.from} from`),
  ];
}

/** Where the tooltip of a node goes on the full pitch. */
export function nodeTooltipPlace(node: PassNode, maxPasses: number): TooltipPlace {
  return tooltipPlaceAt(toPitchPoint(node.x, node.y), nodeRadius(node.passes, maxPasses), "full");
}

/** The chart in words. It holds counts from the spec and the minimum the visitor chose. */
export function summaryText(spec: PassNetworkSpec, minPasses: number): string {
  if (spec.nodes.length === 0) return "This network has no passes.";
  const allLinks = links(spec);
  const [most] = nodeOrder(spec.nodes);
  const players = `${spec.nodes.length} ${spec.nodes.length === 1 ? "player" : "players"}`;
  const linkCount =
    allLinks.length === 0
      ? "no passing links"
      : `${allLinks.length} ${allLinks.length === 1 ? "passing link" : "passing links"}`;
  const parts = [
    `${windowText(spec)}.`,
    `${players}, ${linkCount}.`,
    `Most passes: ${most.player} (${most.passes}).`,
  ];
  const [strongest] = allLinks;
  if (strongest) {
    parts.push(
      `Strongest link: ${strongest.a} and ${strongest.b} (${passesText(strongest.passes)}).`,
    );
  }
  const shown = visibleLinks(allLinks, minPasses).length;
  if (shown < allLinks.length) {
    parts.push(
      `${shown} of ${allLinks.length} links shown, each with at least ${passesText(minPasses)}.`,
    );
  }
  return parts.join(" ");
}
