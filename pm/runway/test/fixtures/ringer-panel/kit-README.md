# Adversarial-review panel (cross-review-gate dispatch)

The two-seat instantiation of the clone's `ringer/templates/adversarial-review`
kit, as specified by the library skill
`_Core/library/skills/agent-operations/cross-review-gate` ("Dispatch via
Ringer (panel path)"). The upstream kit is N same-engine seats varied by
model; this panel is two seats covering two diversity axes:

- `review-codex` — engine `codex`, model **`gpt-6-astra`**: cross-vendor
  detection. Pinned in the manifest so scoreboard attribution stays exact
  even if the config default drifts; `gpt-5.6-sol` is the fallback.
- `review-claude` — engine `claude`, model **`claude-fable-5`**:
  fresh-context detection.

Astra + Fable are the house defaults for every panel (Joe's direction,
2026-09-06 — these are the two models he runs most). Downgrade the Claude
seat to `claude-sonnet-5` only when quota is tight and the boundary touches
no live data; the 2026-07-27 bakeoff showed Fable's sole-finder catches were
exactly the operational tail (migrations, deploys, schema).

## Fill in

| Placeholder | What goes there |
|---|---|
| `{{RUN_SLUG}}` | Stable slug, e.g. `2026-07-27-billing-migration` |
| `{{WORKDIR}}` | Scratch dir OUTSIDE the repo under review |
| `{{REVIEW_SCOPE}}` | Human-readable name of the thing under review |
| `{{ARTIFACT_PATH_OR_DIFF_COMMAND}}` | Exact diff / paths / command every seat inspects |
| `{{BRIEF}}` | The FULL text of `.review-gate/<slug>/brief.md`, inlined — specs must be self-contained; same brief in both seats |
| `{{REVIEW_FOCUS}}` | One-line focus (what the gate is guarding) |
| *(seat models)* | Already pinned: `gpt-6-astra` / `claude-fable-5`. Edit the `model` fields only to downgrade a seat deliberately. |
| `{{KIT_DIR}}` | Absolute path to the clone kit: this repo's `templates/adversarial-review` (its `checks/` validator is reused verbatim) |

## Rules from the skill (non-negotiable)

- Both seat specs open with the worker preamble (upstream #111): a seat
  that reads the repo's `CLAUDE.md` / `.claude/` can decide it is the
  orchestrator and stall to timeout. Keep the preamble in place when you
  fill the template; it is worded for a read-only review seat.

- **Freeze the artifact while the panel is in flight** — a fix applied
  mid-run contaminates any late-finishing seat.
- Offer at a stage boundary, dispatch only on the user's yes.
- After the run: copy each seat's `report.md` verbatim into
  `.review-gate/<slug>/` as `review-codex.md` / `review-claude.md`; triage
  the merged set with a flagged-by column. Both-seats findings are the
  strongest Agree candidates; claude-seat-only findings get extra scrutiny
  (shared family priors).
- PASS means the report satisfied the findings contract — it does not mean
  the artifact is good; the triage verdict stays with the orchestrator.

Lint before running: `python3 …/ringer/ringer.py lint <filled-manifest>`.
