# Changelog

All notable changes to the Highbury web app at
[highbury.arkaslittlemind.com](https://highbury.arkaslittlemind.com) are recorded
here: what a visitor sees and can do, including the behaviour of the analyst API
that shows on the page. Internal tooling, tests, and data-loading changes are
left out unless they change an answer.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). A
minor version marks a milestone of the build plan or a new capability, and a
patch version marks fixes only. Each push to `main` deploys the web app, so each
version below is a production release, and the Git tag of the same name (such as
`v1.4.1`) marks its last commit.

## [Unreleased]

## [1.4.1] - 2026-11-08

### Changed

- The hero shows a painting of Highbury and the Emirates side by side, the two
  eras of the headline, in place of the drawn grass and chalk lines.
- The "Two seasons. Honest about the gaps." section shows a painting of the
  2025-26 title parade. Its shade is light around the season cards, so the
  painting keeps its colour, and dark behind the heading and the footnote.
- The header has a third link, FAQ, and its middle link sits on the centre line
  of the page. The footer FAQ link lands on the same place as the header one.

### Fixed

- The hero headline and intro are easy to read on the painting. A dark glow
  behind the centred text keeps the brushstrokes out of the letters, a soft text
  shadow separates each line, and the intro uses the same off-white as the
  headline.
- The season cards no longer cut off their source badge and bottom box on small
  phones or just above 760 px wide. The badge moves under the season when the
  two do not fit on one line.

## [1.4.0] - 2026-11-07

The landing page redesign.

### Added

- A centred hero with the question bar and the example questions under it, a
  glass header with the site logo, and a checked sample answer (Henry v
  Liverpool, 9 April 2004) that computes its four claims from the sample shots.
- Four capability cards: ask in plain English, charts from the data, compare the
  two eras, and checks every number. Each card plays a small live demo on hover,
  focus, or first view on a touch screen, and its Try link puts the question in
  the hero bar.
- Season cards with the record of each season and what its data holds and lacks.
- A chart gallery with one small chart of each type, built from the agent's own
  queries, each with its question as a Try link.
- A proof band with the evaluation results of the production model and the date
  of the run.
- A FAQ and a footer with the product, data, and source links, a status line
  that says whether the analyst is online, and a visit count.
- Painted backgrounds behind the Seasons and FAQ sections and the footer.

### Changed

- The site fonts are Archivo for headings and Figtree for text.
- The first view plays one staggered rise of the hero. With reduced motion, the
  parts only fade in.

### Removed

- The "How it works" strip and the separate sample-answer section, which the
  capability cards and the hero card replace.

## [1.3.0] - 2026-11-02

The public launch.

### Added

- A Cloudflare Turnstile bot check before each question. Most visitors see
  nothing; a visitor that Cloudflare flags gets a checkbox.
- Daily limits for each address and for the whole site, and at most 10
  questions answered at one time. The example questions keep their stored
  answers and do not count toward the limits.
- A "Daily limit" card when a daily limit refuses a question. It has no retry
  button, because the same question meets the same limit until midnight UTC.
- A clear message when the model provider has no credit left.
- Search and social metadata: a canonical address, Open Graph and Twitter cards
  with a preview image, `robots.txt`, and a sitemap.
- A text copy of the page for AI agents at `/index.md` (also `/` with
  `Accept: text/markdown`), `/llms.txt`, and `/llms-full.txt`, plus JSON-LD.
  AI search crawlers are allowed and AI training crawlers are blocked.

### Security

- Security headers on every page: a Content-Security-Policy that allows only the
  site, the analyst API, Cloudflare Turnstile, and Cloudflare Web Analytics, and
  denies framing.
- Every high dependency advisory is fixed.

### Fixed

- The Content-Security-Policy allows the Cloudflare Web Analytics script.

## [1.2.0] - 2026-11-01

Player maps and richer metrics.

### Added

- A pass map of one player's 2003-04 passes, with completed and incomplete
  passes told apart and filters such as long passes.
- A touch heatmap of one player's 2003-04 touches in zones of the pitch.
- More 2003-04 metrics in answers: chances created, duels and aerial duels won,
  pass accuracy, and accurate long balls.
- More 2025-26 metrics in answers: chances created, and FPL tackles, recoveries,
  and clearances, blocks, and interceptions.
- A Show all button in the shot map legend that turns every outcome back on.

### Changed

- Icons appear only where they show a state (a claim passed or removed, a step
  done, a row that opens, a caveat). The site's own marks replace the icon
  library.
- The hero names both seasons, and its badge is gone.

### Fixed

- Browser Back from an answer returns to the landing page with the question in
  the bar, instead of leaving the site.
- The heatmap scale key matches the shades of its zones.
- The analyst no longer spends tool calls on lookups it already has in its
  prompt or on checking its own numbers, so answers need fewer steps and fewer
  questions run out of steps before they answer.

## [1.1.1] - 2026-10-26

### Changed

- The answer screen has the look of the landing screen: the same pill for the
  follow-up bar, buttons that respond on press, and chevrons on the expandable
  details.
- The page feels native on a phone: a dark browser bar, no grey tap highlight,
  taps that act at once, and a follow-up bar clear of the home indicator and
  the notch.
- The page names all four data sources.
- A conversation ends after 20 turns.

### Fixed

- Reduced motion keeps feedback: movement becomes a fade instead of nothing.
- A long answer no longer drops its stream while the agent is quiet. The API
  sends a heartbeat that keeps the connection open through the load balancer.

## [1.1.0] - 2026-10-25

Finished charts and wider data.

### Added

- An xG timeline of one match: each team's cumulative xG by minute, with every
  shot and goal marked.
- A points-pace chart: cumulative league points by matches played, for Arsenal
  in both seasons and a rival or that season's leader.
- The pass network shows the starting XI by default, with a minimum-passes
  control and a table of the drawn links.
- Answers about every league match of both seasons: results, the table, and team
  match stats such as shots, corners, fouls, and cards.
- Answers about 2025-26 FPL data: clean sheets, saves, bonus points, cards, FPL
  points, and price.

### Security

- Next.js is upgraded to 16.4.3, which fixes three published advisories.

## [1.0.0] - 2026-10-15

The first release: ask a question, get a checked answer.

### Added

- The Ask page: a question bar, example questions, live steps while the agent
  works, and an answer with a verification badge, caveats, and follow-ups in the
  same conversation.
- Claim checks: each claimed number links to the query that produced it, and
  "Show the working" lists the tools and the SQL behind the answer.
- A shot map with xG as size and the outcome as shape, a legend that filters by
  outcome, keyboard navigation, and a text summary.
- Compare bars for two players on shared metrics, with the xG model of each
  season named.
- A pass network of one 2003-04 match: players at their average position and a
  line for each passing pair.
- A landing screen with the question bar in a grass hero, how it works, the two
  seasons, and a sample answer, laid out for phones too.
- Reduced-motion support and a football favicon.
- A limit of 5 questions a minute for each address, and a size limit on each
  request.

[Unreleased]: https://github.com/arkaslittlemind/Highbury/compare/v1.4.1...HEAD
[1.4.1]: https://github.com/arkaslittlemind/Highbury/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/arkaslittlemind/Highbury/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/arkaslittlemind/Highbury/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/arkaslittlemind/Highbury/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/arkaslittlemind/Highbury/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/arkaslittlemind/Highbury/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/arkaslittlemind/Highbury/releases/tag/v1.0.0
