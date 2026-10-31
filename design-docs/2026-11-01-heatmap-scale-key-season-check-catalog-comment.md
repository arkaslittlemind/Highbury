# Heatmap scale key, season check, catalog comment

| | |
| --- | --- |
| Work | Fix: three P3 findings from the reviews of items 25 and 26, in one change |
| Change | `5fe3dd8` on `main` (squash of `f00e49e` from `fix/heatmap-scale-key-season-check-catalog-comment`), 2026-11-01 |
| Evidence | `blueprint/history/fixes/heatmap-scale-key-season-check-catalog-comment.md` (spec and the three closed findings. Local, not in Git). The commit message. The build conversation. |
| Reader | A learner who can write basic code and is new to this stack |

This document obeys the rules of ASD-STE100 Simplified Technical
English. It is not a certified STE document.

## 1. Summary

This fix closes three small findings. The scale key of the heatmap now starts at
the shade of the quietest zone, not at the shade of 0 touches. The heatmap
builder now tells the agent what to do when the rows have two seasons, and a
test reaches that check. A comment in the catalog code now sits above the block
that it describes.

The one idea to remember: the key and the zones now use one function for their
shade. Thus they cannot show different shades for the same count.

## 2. Why this work exists

The independent review of item 26 recorded F-02 and F-03. The independent review
of item 25 recorded F-01. All three are P3, so none of them blocked a merge.
Source: the findings in the fix archive.

- **F-02:** the left end of the scale key had the shade for 0 touches, but its
  label gave the fewest count. If the quietest zone has 20 touches of a busiest
  60, no zone on the pitch has that faint shade.
- **F-03:** the builder refused rows of two seasons, but no test reached that
  check. `AGENTS.md` says that Python logic ships with a test.
- **F-01:** the comment that gives the shape of a `CATALOG` row sat above
  `ADVANCED_ROWS`, which has a different shape.

## 3. Design

The fix changes four places. Each change is small and has one job.

| Part | Location | Job |
| --- | --- | --- |
| Key shades | `apps/web/src/lib/heatmap.ts` | `keyOpacities` gives the shades of the key through `zoneOpacity` |
| Scale key | `apps/web/src/components/charts/heatmap.tsx` | Draws the key with the shades of `keyOpacities` |
| Season check | `services/analyst/src/analyst/charts.py` | Adds the remedy "Filter on one season." to the error |
| Catalog comment | `ingest/src/ingest/curated.py` | Puts the row-shape comment above `CATALOG` |

`zoneOpacity` is the function that gives each zone its shade. It maps 0 touches
to 0.15 and the busiest zone to 0.85. `keyOpacities` takes five counts evenly
from the fewest to the most. Then it gives each count to `zoneOpacity`. Thus the
left end of the key is the shade of the quietest zone, and the right end is the
shade of the busiest zone.

## 4. Workflow

Example input: a heatmap where the quietest zone has 20 touches and the busiest
zone has 60.

1. `Heatmap` finds the fewest count (20) and the most (60). (`heatmap.tsx:138`)
2. `ScaleKey` asks `keyOpacities` for five shades. (`heatmap.tsx:31`)
3. `keyOpacities` makes the counts 20, 30, 40, 50, and 60. (`heatmap.ts:42`)
4. `zoneOpacity` turns each count into a shade. (`heatmap.ts:34`)
5. The key draws five rects, from about 0.38 to 0.85.

A zone with 20 touches on the pitch also gets about 0.38. Before the fix, the
left end of the key was 0.15.

## 5. Decisions and tradeoffs

### 5.1 The key reuses the zone function

- **Choice:** `keyOpacities` calls `zoneOpacity` for each step of the key.
- **Alternatives:** Label the left end of the key with 0 and keep the old shades. The review gave this as a second option.
- **Reason:** Recorded: if the key uses the opacity of the zones, the key and the zones cannot drift apart. Source: the fix spec, The fix.
- **Cost:** The key no longer shows the full range of shades. A chart where every zone is near the busiest gets a key of near-equal shades.

### 5.2 Equal counts give the strongest shade

- **Choice:** When every zone has the same count, every step of the key is 0.85.
- **Alternatives:** Show a range of shades even when all zones are equal.
- **Reason:** Recorded: every zone on the pitch then has the strongest shade, so the key must match. Source: the fix spec and the second `keyOpacities` test.
- **Cost:** The key shows one shade. The two labels still give the count.

### 5.3 The season error names its remedy

- **Choice:** The season error now ends with "Filter on one season."
- **Alternatives:** Keep the message and only add the test.
- **Reason:** Recorded: the player error already says "filter on one player", so the agent knows how to correct its query. Source: F-03 in the fix archive.
- **Cost:** None found.

## 6. Blast radius

### 6.1 This work needs

| Dependency | Used for | If it fails |
| --- | --- | --- |
| `zoneOpacity` | The shades of the key | If its range changes, the key changes with it. This is the purpose of the fix |
| `KEY_STEPS` | The count of steps | It is the constant 5. A value of 1 divides by 0 |

### 6.2 These things use this work

| Consumer | Uses | Found in |
| --- | --- | --- |
| `ScaleKey` | `keyOpacities` | `apps/web/src/components/charts/heatmap.tsx:31` |
| The agent | The season error text | `services/analyst/src/analyst/charts.py:323` |

### 6.3 If you change this work

| If you change | Then check |
| --- | --- |
| `KEY_STEPS` | Keep it at 2 or more, because `keyOpacities` divides by `steps - 1` |
| The season error | The test case at `test_charts.py:779` compares the full text |

### 6.4 How to remove this work

Revert `5fe3dd8`. No data, catalog row, or configuration changed.

## 7. Code reading path

1. [`apps/web/src/lib/heatmap.ts:34`](../apps/web/src/lib/heatmap.ts#L34) - Look for: the range of `zoneOpacity`.
2. [`apps/web/src/lib/heatmap.ts:42`](../apps/web/src/lib/heatmap.ts#L42) - Look for: how `keyOpacities` takes five counts from fewest to most.
3. [`apps/web/src/lib/heatmap.test.ts:49`](../apps/web/src/lib/heatmap.test.ts#L49) - Look for: the two ends, the rise, and the equal-count case.
4. [`apps/web/src/components/charts/heatmap.tsx:31`](../apps/web/src/components/charts/heatmap.tsx#L31) - Look for: the key that maps the shades to rects.
5. [`services/analyst/src/analyst/charts.py:323`](../services/analyst/src/analyst/charts.py#L323) - Look for: the remedy in the season error.
6. [`ingest/src/ingest/curated.py:65`](../ingest/src/ingest/curated.py#L65) - Look for: the comment above `CATALOG`.

## 8. Known limits

- The browser view of the new key was not checked, because it needs the servers and one paid question. The unit tests prove the two ends.
- `keyOpacities` does not guard against `steps` of 1. Only the constant 5 calls it.
- The production API and web show the fix only after a new image and a push of `main`.

## 9. Self-test

1. Why does the key call `zoneOpacity` and not compute its own shades?
2. What does the key show when every zone has the same count?
3. What happens if `KEY_STEPS` becomes 1?
4. Why does the season error now end with a remedy?
5. What must you revert to remove this fix?

<details>
<summary>Answers</summary>

1. One function for both makes the key and the zones show the same shade for a count. See section 5.1.
2. Every step is the strongest shade, as every zone is. See section 5.2.
3. `keyOpacities` divides by 0 and the shades are not numbers. See section 6.3.
4. The agent then knows how to correct its query, as with the player error. See section 5.3.
5. Only `5fe3dd8`, because no data or configuration changed. See section 6.4.

</details>
