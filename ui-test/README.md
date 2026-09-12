# ui-test

Agent-run UI tests for FileMaker Pro builds, with evidence instead of claims.

**Skill:** `fm-ui-test` — three seats that never merge. The builder (Claude Code)
writes a typed test instruction; a Codex computer-use worker runs it under Ringer
and returns a receipt (screenshots + values read off the screen, each tagged
accessibility or pixels); executed checks validate the receipt; a separate
verifier task transcribes the screenshots itself and issues the verdict.
Outcomes: `PASS-OBSERVED` / `FAIL` / `BLOCKED` — a test that could not run is
never a product failure and never a pass.

What ships:

| Path | Purpose |
|---|---|
| `skills/fm-ui-test/SKILL.md` | the workflow and the rules the probe runs taught |
| `references/tool-matrix.md` | what each seat can actually do on this stack (Codex computer-use, Claude computer-use MCP, AppleScript, Data API, OttoFMS), observed 2026-09-12 |
| `references/instruction-template.md` | the runner spec shape |
| `references/receipt-schema.md` | `truth.json`, `receipt.json`, `verdict.json` |
| `references/manifest-template.json` | two-task Ringer manifest: run, then verify |
| `scripts/check_receipt.py` | Ringer check for the run task (receipt validity) |
| `scripts/check_verdict.py` | Ringer check for the verify task (the product pass) |

## Assumes

- **Ringer** (see the repo README) — every runner and verifier is a Ringer task.
- **Codex computer-use approved for FileMaker Pro with "always" scope**, granted
  once in the interactive Codex CLI. Desktop-app approvals are session-scoped and
  headless `codex exec` auto-declines the prompt.
- A FileMaker file open in FileMaker Pro on the same Mac; one GUI worker at a time.
- For hosted files, `fm-dc`'s `fm-dataapi` / `fm-otto` for data assertions and resets.

## Install

```
/plugin install ui-test@dc-plugins
```
