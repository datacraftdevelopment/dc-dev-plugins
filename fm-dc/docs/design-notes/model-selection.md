# Model selection for fm-dc agents

**Status:** convention (adopted 2026-07-24)
**Applies to:** every agent shipped in `agents/`
**Source:** distilled from Claris *"Community Live 49: Inside the AI coding agent"* (public webinar, 2026-07-23) — architecture/principle only, no toolkit code (clean-room, SCOPE §10).

---

## The principle

A subagent inherits the session model unless it pins its own. Don't run every agent on the most capable model "to be safe" — capable models are slower and drain the subscription's token allotment faster. Match the model to the *kind of thinking* the agent does:

| Kind of work | Model | Why |
|---|---|---|
| Troubleshooting, brainstorming, architecture, scoping a plan | `opus` (or session default) | open-ended reasoning; a wrong turn here is expensive downstream |
| Writing a spec from a settled intent | `sonnet` | structured, but still judgment |
| Mechanical execution of an already-chunked plan; running deterministic tools and reporting | `sonnet` → `haiku` | little interpretation left; the tools do the work |

The FileMaker payoff of the deterministic-tools design (see [the export/patch harness note](filemaker-xml-export-patching-harness.md) and `genobj`): once XML *shape* is compiled by a tool instead of guessed by the model, **the model's job shrinks to gauging intent** — so a mid-tier model is enough, and only *logic* can be wrong, never *syntax*.

## What each shipped agent pins, and why

- **`fm-patch-builder` → `sonnet`.** Pure mechanical execution: it acts only on an operator-approved `selection.json`, runs the FMUpgradeTool SOP (backup → validate → smoke → apply → verify by re-export), and reports compactly. No open-ended reasoning; the safety comes from the deterministic pipeline, not from model horsepower.
- **`fm-xml-validator` → `sonnet`.** Its teeth are deterministic — `fmlint`, scoped re-export, re-diff. The model orchestrates those and reads the results adversarially; Sonnet is sufficient. Bump to `opus` for a paranoid final gate on a high-stakes production deploy.

## Overriding

Two knobs:

1. **Per-agent, durably** — the `model:` line in the agent's front matter (what this note governs). Bump or drop it when the agent's job changes.
2. **Per-task, in conversation** — just tell the harness: *"use opus to scope this, then switch to sonnet to build it."* This is the video's own recommended habit, and it covers the main-conversation work that isn't inside a pinned agent.

## Forward note

When the **schema-builder** agent lands (SCOPE Phase 4) it does open-ended work — turning "build me an invoicing system" into tables, fields, and relationships. That one should pin **`opus`** (or inherit a capable default), not Sonnet. The rule tracks the *work*, not the agent count: pin down for mechanical, pin up for interpretive.
