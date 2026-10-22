import { describe, expect, it } from "vitest";

import {
  defaultMinPasses,
  LABEL_SIZE,
  labelOffset,
  labelSides,
  linkStyle,
  links,
  nodeLabel,
  nodeOrder,
  nodeRadius,
  nodeTooltipPlace,
  partners,
  shortName,
  summaryText,
  tooltipLines,
  visibleLinks,
  windowText,
  type Link,
  type PassNetworkSpec,
} from "@/lib/pass-network";

const VIEIRA = { player: "Patrick Vieira", x: 60, y: 40, passes: 48 };
const PIRES = { player: "Robert Pirès", x: 78.5, y: 18, passes: 31 };
const COLE = { player: "Ashley Cole", x: 50, y: 5, passes: 31 };

function network(changes: Partial<PassNetworkSpec> = {}): PassNetworkSpec {
  return {
    type: "pass_network",
    id: "chart_3",
    title: "Arsenal passes against Liverpool",
    nodes: [VIEIRA, PIRES, COLE],
    edges: [
      { source: "Patrick Vieira", target: "Robert Pirès", passes: 9 },
      { source: "Robert Pirès", target: "Patrick Vieira", passes: 4 },
      { source: "Ashley Cole", target: "Robert Pirès", passes: 6 },
    ],
    ...changes,
  };
}

describe("links", () => {
  it("makes one link for each pair, with the passes in each direction", () => {
    expect(links(network())).toEqual([
      { a: "Patrick Vieira", b: "Robert Pirès", aToB: 9, bToA: 4, passes: 13 },
      { a: "Ashley Cole", b: "Robert Pirès", aToB: 6, bToA: 0, passes: 6 },
    ]);
  });

  it("leaves out an edge to a player who is not a node, and an edge to the same player", () => {
    const spec = network({
      edges: [
        { source: "Patrick Vieira", target: "Dennis Bergkamp", passes: 5 },
        { source: "Dennis Bergkamp", target: "Patrick Vieira", passes: 2 },
        { source: "Patrick Vieira", target: "Patrick Vieira", passes: 1 },
        { source: "Ashley Cole", target: "Patrick Vieira", passes: 3 },
      ],
    });

    expect(links(spec)).toEqual([
      { a: "Ashley Cole", b: "Patrick Vieira", aToB: 3, bToA: 0, passes: 3 },
    ]);
  });

  it("orders links with the same passes by name", () => {
    const spec = network({
      edges: [
        { source: "Robert Pirès", target: "Patrick Vieira", passes: 2 },
        { source: "Ashley Cole", target: "Robert Pirès", passes: 2 },
      ],
    });

    expect(links(spec).map((link) => link.a)).toEqual(["Ashley Cole", "Patrick Vieira"]);
  });

  it("is empty for a network with no edges", () => {
    expect(links(network({ edges: [] }))).toEqual([]);
  });
});

describe("nodeOrder", () => {
  it("goes from the most passes to the fewest, and by name for the same passes", () => {
    expect(nodeOrder([PIRES, COLE, VIEIRA]).map((node) => node.player)).toEqual([
      "Patrick Vieira",
      "Ashley Cole",
      "Robert Pirès",
    ]);
  });
});

describe("nodeRadius", () => {
  it("goes from 1.5 to 4.5 with the area in proportion to the passes", () => {
    expect(nodeRadius(0, 48)).toBe(1.5);
    expect(nodeRadius(48, 48)).toBe(4.5);
    expect(nodeRadius(12, 48)).toBe(3);
  });
});

describe("linkStyle", () => {
  it("is thin and faint for 1 pass and wide and strong for the most passes", () => {
    expect(linkStyle(1, 13)).toEqual({ width: 1, opacity: 0.25 });
    expect(linkStyle(13, 13)).toEqual({ width: 6, opacity: 0.9 });
  });

  it("is the thin line when the most passes on a link is 1", () => {
    expect(linkStyle(1, 1)).toEqual({ width: 1, opacity: 0.25 });
  });
});

describe("labelOffset", () => {
  it("puts the baseline below the node, or just above it", () => {
    expect(labelOffset("below", 3)).toBe(3 + LABEL_SIZE);
    expect(labelOffset("above", 3)).toBeCloseTo(-3.6);
  });
});

describe("labelSides", () => {
  it("puts the name of each node apart from the others below the node", () => {
    expect(labelSides([VIEIRA, PIRES, COLE], 48)).toEqual(
      new Map([
        ["Patrick Vieira", "below"],
        ["Ashley Cole", "below"],
        ["Robert Pirès", "below"],
      ]),
    );
  });

  it("puts a name above its node when the place below is taken, else leaves it off", () => {
    // Three players at nearly one place, as Henry, Pires, and Edu can be.
    const nodes = [
      { player: "Robert Pirès", x: 68, y: 20, passes: 40 },
      { player: "Thierry Henry", x: 70, y: 21, passes: 30 },
      { player: "Eduardo Gaspar", x: 69, y: 19, passes: 10 },
    ];

    expect(labelSides(nodes, 40)).toEqual(
      new Map([
        ["Robert Pirès", "below"],
        ["Thierry Henry", "above"],
      ]),
    );
  });
});

describe("shortName", () => {
  it("is the last word of the name", () => {
    expect(shortName("Thierry Henry")).toBe("Henry");
    expect(shortName(" Robert  Pirès ")).toBe("Pirès");
    expect(shortName("Kanu")).toBe("Kanu");
  });
});

describe("partners", () => {
  it("gives the passes to and from each partner of a player", () => {
    expect(partners("Robert Pirès", links(network()))).toEqual([
      { player: "Patrick Vieira", to: 4, from: 9, passes: 13 },
      { player: "Ashley Cole", to: 0, from: 6, passes: 6 },
    ]);
  });
});

describe("nodeLabel", () => {
  it("names the passes and the top links of a player", () => {
    expect(nodeLabel(PIRES, links(network()))).toBe(
      "Robert Pirès, 31 passes made. Top links: Patrick Vieira, 4 to and 9 from; Ashley Cole, 0 to and 6 from.",
    );
  });

  it("names only the passes of a player with no link", () => {
    expect(nodeLabel({ ...VIEIRA, passes: 1 }, [])).toBe("Patrick Vieira, 1 pass made.");
  });
});

describe("tooltipLines", () => {
  it("has the name, the passes, and the top partners with short names", () => {
    expect(tooltipLines(VIEIRA, links(network()))).toEqual([
      "Patrick Vieira",
      "48 passes made",
      "Pirès · 9 to, 4 from",
    ]);
  });
});

describe("nodeTooltipPlace", () => {
  it("places the tooltip on the full pitch", () => {
    // Vieira at the centre spot: 40, 60 in a box of 84 x 126 from -2, -4, radius 4.5.
    const place = nodeTooltipPlace(VIEIRA, 48);

    expect(place.side).toBe("above");
    expect(place.left).toBeCloseTo(50);
    expect(place.top).toBeCloseTo((59.5 / 126) * 100);
  });
});

function link(a: string, b: string, aToB: number, bToA: number): Link {
  return { a, b, aToB, bToA, passes: aToB + bToA };
}

describe("defaultMinPasses", () => {
  it("is 3 when a link has at least 3 passes", () => {
    expect(defaultMinPasses([link("A", "B", 2, 0), link("A", "C", 9, 4)])).toBe(3);
  });

  it("is the most passes on a link when that is below 3, so a line is still drawn", () => {
    expect(defaultMinPasses([link("A", "B", 1, 1), link("A", "C", 1, 0)])).toBe(2);
  });

  it("is 1 for a network with no links", () => {
    expect(defaultMinPasses([])).toBe(1);
  });
});

describe("visibleLinks", () => {
  const all = [link("A", "B", 9, 4), link("A", "C", 2, 1), link("B", "C", 1, 0)];

  it("keeps the links with at least the minimum passes, both directions together", () => {
    expect(visibleLinks(all, 3)).toEqual([all[0], all[1]]);
  });

  it("keeps the order of links(), so the table lists the lines in the same order", () => {
    const ordered = links(network());
    expect(visibleLinks(ordered, 1).map((each) => [each.a, each.b])).toEqual(
      ordered.map((each) => [each.a, each.b]),
    );
  });

  it("keeps every link at 1, and none above the most passes", () => {
    expect(visibleLinks(all, 1)).toEqual(all);
    expect(visibleLinks(all, 14)).toEqual([]);
  });
});

describe("windowText", () => {
  it("names the minute of the first substitution", () => {
    expect(windowText(network({ until_minute: 71 }))).toBe(
      "Passes before the first substitution, 71'",
    );
  });

  it("is the whole match with no minute, also for a spec from before the field", () => {
    expect(windowText(network({ until_minute: null }))).toBe("Whole match");
    expect(windowText(network())).toBe("Whole match");
  });
});

describe("summaryText", () => {
  it("counts the players and links, and names the most passes and the strongest link", () => {
    expect(summaryText(network({ until_minute: 71 }), 1)).toBe(
      "Passes before the first substitution, 71'. 3 players, 2 passing links. Most passes: Patrick Vieira (48). Strongest link: Patrick Vieira and Robert Pirès (13 passes).",
    );
  });

  it("says how many links the minimum hides", () => {
    expect(summaryText(network(), 7)).toBe(
      "Whole match. 3 players, 2 passing links. Most passes: Patrick Vieira (48). Strongest link: Patrick Vieira and Robert Pirès (13 passes). 1 of 2 links shown, each with at least 7 passes.",
    );
  });

  it("says when there are no links", () => {
    expect(summaryText(network({ nodes: [VIEIRA], edges: [] }), 1)).toBe(
      "Whole match. 1 player, no passing links. Most passes: Patrick Vieira (48).",
    );
  });

  it("says when the network is empty", () => {
    expect(summaryText(network({ nodes: [], edges: [] }), 1)).toBe("This network has no passes.");
  });
});
