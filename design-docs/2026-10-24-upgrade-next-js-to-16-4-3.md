# Upgrade Next.js to 16.4.3

| | |
| --- | --- |
| Work | Fix: move the web app from Next.js 16.4.0 to 16.4.3 to close three security advisories |
| Change | `64e4732` on `main` (squash of `7d98a88`, base `7ae5fb8`), 2026-10-24 |
| Evidence | `blueprint/history/fixes/upgrade-next-js-to-16-4-3.md` (fix spec and completion record. Local, not in Git). The commit message. The build conversation, with the output of `pnpm audit`. |
| Reader | A learner who can write basic code and is new to this stack |

This document obeys the rules of ASD-STE100 Simplified Technical
English. It is not a certified STE document.

## 1. Summary

This fix changes two version pins in `apps/web/package.json`: `next` and
`eslint-config-next` go from `16.4.0` to `16.4.3`. The lock file changes only
the packages of Next.js. No source file changes. The one idea to remember: a
patch release on the same minor line closes the advisories with no code change.

## 2. Why this work exists

During feature 20, `pnpm build` and `pnpm dev` stopped one time with a security
notice from Next.js. Then `pnpm audit --prod` named three advisories on
`next@16.4.0`. An advisory is a public report of a security defect in a package.
It names the versions that have the defect and the versions that fix it.

- Critical: remote code execution with no login, in the Image Optimization API, when the app uses SVG files.
- Critical: remote code execution with no login, in `use cache` functions that return typed arrays.
- High: denial of service in the App Router, through Server Actions.

All three affect `>=16.0.0 <=16.4.0`, and `16.4.1` patches them. The public web
app on Vercel ran `16.4.0`. Recorded: fix spec, The problem.

## 3. Design

The fix has no new part. It changes the versions that two parts of the web app
use.

| Part | Location | Job |
|---|---|---|
| Version pins | `apps/web/package.json` | Name the exact versions of `next` and `eslint-config-next` |
| Lock file | `apps/web/pnpm-lock.yaml` | Fix the exact version of each package and its dependencies for every install |
| Lint config | `apps/web/eslint.config.mjs` | Loads the rules of `eslint-config-next`, which must match the version of `next` |

A lock file records the exact version of each installed package. Thus Vercel
and each developer install the same packages. This fix uses it to move only
the Next.js packages.

## 4. Workflow

Example input: a push to `main` after this fix.

1. Vercel reads `apps/web/pnpm-lock.yaml` and installs `next@16.4.3`. ([`package.json:19`](../apps/web/package.json#L19))
2. Vercel runs `pnpm build`, which runs `next build`. ([`package.json:7`](../apps/web/package.json#L7))
3. The build completes with no security notice.
4. Vercel replaces production with the new build.

The fix ran these checks before the merge:

- `pnpm audit --prod` showed no advisory on `next`.
- `pnpm build`, `pnpm lint`, and `pnpm test` passed. The tests were 263 of 263.
- `pnpm dev` started on 16.4.3 with no notice, and the home page loaded with no console error.

## 5. Decisions and tradeoffs

### 5.1 The newest patch on the same minor line

- **Choice:** Pin `16.4.3`, the `latest` dist-tag of `next`.
- **Alternatives:** Pin `16.4.1`, the first patched version. Or move to a new minor line.
- **Reason:** Recorded: `16.4.3` is the newest patch of the 16.4 line, and a patch on the same line needs no code change. Source: fix spec, The fix.
- **Cost:** The two later patches can bring changes that this fix did not read. The build, lint, tests, and the dev server showed no change.

### 5.2 `pnpm add` with exact versions

- **Choice:** Run `pnpm add -E` for each package.
- **Alternatives:** Run `next upgrade --agent=security`, which the notice suggested.
- **Reason:** Recorded: with `pnpm add`, the diff is only the two version pins and the lock file. Source: fix spec, The fix.
- **Cost:** None seen. The lock diff showed only `next`, the `@next/*` packages, and `eslint-config-next`.

### 5.3 The other advisories stay out of scope

- **Choice:** The fix closes only the three advisories on `next`.
- **Alternatives:** Also update the packages under the `shadcn` CLI.
- **Reason:** Recorded: the other 10 advisories come through `shadcn`, not through `next`. The user approved the narrow scope. Source: fix spec, and the build conversation.
- **Cost:** `pnpm audit --prod` still reports 10 advisories, 4 of them high.

## 6. Blast radius

### 6.1 This work needs

| Dependency | Used for | If it fails |
|---|---|---|
| The npm registry | The packages of `next@16.4.3` | `pnpm install` stops, and Vercel cannot build |
| React `19.3.0` | The runtime that Next.js uses | The fix did not change React. A mismatch stops the build. |

### 6.2 These things use this work

| Consumer | Uses | Found in |
|---|---|---|
| `dev`, `build`, `start` scripts | The `next` command | [`package.json:6`](../apps/web/package.json#L6) |
| Lint config | The rules of `eslint-config-next` | [`eslint.config.mjs:2`](../apps/web/eslint.config.mjs#L2) |
| Vercel project `highbury` | The build of `apps/web` on each push to `main` | `AGENTS.md`, Commands |

### 6.3 If you change this work

| If you change | Then check |
|---|---|
| The version of `next` | That `eslint-config-next` has the same version, and that `pnpm audit --prod` shows no advisory on `next` |
| The minor line of `next` | The Next.js docs in `node_modules/next/dist/docs/`, as `apps/web/AGENTS.md` requires |

### 6.4 How to remove this work

Revert `64e4732`, then push `main`. Do not do this: the old version has the
three advisories.

## 7. Code reading path

1. [`package.json:19`](../apps/web/package.json#L19) - Look for: the exact pin of `next`, with no caret.
2. [`package.json:33`](../apps/web/package.json#L33) - Look for: the pin of `eslint-config-next`, at the same version.
3. [`eslint.config.mjs:2`](../apps/web/eslint.config.mjs#L2) - Look for: where the lint rules of Next.js come in.

## 8. Known limits

- `pnpm audit --prod` still reports 10 advisories through the `shadcn` CLI (decision 5.3).
- The fix did not read the release notes of 16.4.2 and 16.4.3. Only the checks in section 4 support them.
- No new finding. The debrief found no new defect.

## 9. Self-test

1. Why does this fix need no change to the source code?
2. Why does the fix use `pnpm add -E` and not the upgrade command that the notice suggested?
3. What must change at the same time as the version of `next`?
4. Why does `pnpm audit --prod` still report advisories after this fix?
5. What closes the advisories on the live site?

<details>
<summary>Answers</summary>

1. The new version is a patch on the same minor line. See section 5.1.
2. The diff is then only the two version pins and the lock file. See section 5.2.
3. The version of `eslint-config-next`, which the lint config loads. See section 6.3.
4. The other 10 advisories come through the `shadcn` CLI, not through `next`. See section 5.3.
5. The push to `main`, because Vercel then builds production with 16.4.3. See section 4.

</details>
