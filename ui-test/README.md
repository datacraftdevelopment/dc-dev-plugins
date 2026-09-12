# ui-test

Agent-run UI tests for any macOS app with a window — native Swift/SwiftUI apps,
FileMaker Pro, Electron — with evidence instead of claims.

**Skill:** `ui-test` — three seats that never merge. The builder (Claude Code)
writes a typed test instruction; a Codex computer-use worker runs it under Ringer
and returns a receipt (screenshots + values read off the screen, each tagged
accessibility or pixels); executed checks validate the receipt; a separate
verifier task transcribes the screenshots itself and issues the verdict.
Outcomes: `PASS-OBSERVED` / `FAIL` / `BLOCKED` — a test that could not run is
never a product failure and never a pass.

What ships:

| Path | Purpose |
|---|---|
| `skills/ui-test/SKILL.md` | the app-agnostic workflow and the rules the probe runs taught |
| `references/targets/filemaker.md`, `native-macos.md` | per-app profiles: what to approve, preconditions to state, the non-UI channel, reset, AX quirks |
| `references/tool-matrix.md` | what each seat can actually do on this stack, observed 2026-09-12; FileMaker-specific channels marked |
| `references/instruction-template.md` | the runner spec shape |
| `references/receipt-schema.md` | `truth.json`, `receipt.json`, `verdict.json` |
| `references/manifest-template.json` | two-task Ringer manifest: run, then verify |
| `scripts/check_receipt.py` | Ringer check for the run task (receipt validity) |
| `scripts/check_verdict.py` | Ringer check for the verify task (the product pass) |

## Assumes

- **Ringer** (see the repo README) — every runner and verifier is a Ringer task.
- **Codex computer-use approved for the target app with "always" scope**, granted
  once per app in the interactive Codex CLI. Desktop-app approvals are session-scoped and
  headless `codex exec` auto-declines the prompt.
- The target app running on the same Mac; one GUI worker at a time.
- FileMaker targets: `fm-dc`'s `fm-dataapi` / `fm-otto` for data assertions and resets.

## Install

```
/plugin marketplace add datacraftdevelopment/dc-dev-plugins
/plugin install ui-test
```
