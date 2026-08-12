# Available context map

What material exists for this engagement and when to load it. **Available ≠ active** — map sources without pulling them all into context; the agent loads the smallest set that supports the task at hand, and this file is the path back to everything omitted. Update when a source's authority, freshness, location, exclusion, or trigger changes — not on a schedule.

| Source | Where | Authority | Fresh as of | Load when | State |
|---|---|---|---|---|---|
| _e.g. Discovery call transcript_ | `_pm/artifacts/transcripts/…` | canonical | 2026-08-01 | scope or requirements questions | active |
| _e.g. Client's legacy spec_ | `resources/research/…` | anecdotal — client calls it outdated | 2024? | only when legacy behavior is disputed | on demand |

**Authority:** `canonical` (wins conflicts) · `supporting` · `anecdotal` · `unknown` (verify before relying on it). **State:** `active` · `on demand` · `excluded` · `inaccessible`.

## Source precedence

_When sources disagree, which wins and why? Name the cases only a person can settle._

## Deliberate exclusions

_What we're **not** loading and why (stale, sensitive, duplicate, out of scope) — each with the condition that would justify another look._

## Known gaps

_Sources known to exist but not yet obtained, located, verified, or approved — with who or what unblocks each._

<!--
Working rules (absorbed from the library's progressive-context-shaping page):
- Minimum context is not the goal. Minimum SUFFICIENT context is.
- Authority, freshness, relevance, and exposure cost are separate judgments.
- Label uncertainty. Never repair a missing source with a confident guess.
- Load more when: a needed fact/definition/acceptance test is missing · two active
  sources conflict · the decision is high-cost · verification fails or a source
  looks stale · the user asks · the task crosses an approval boundary.
-->
