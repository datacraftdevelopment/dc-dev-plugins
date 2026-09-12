---
name: fm-ui-test
description: Use when a FileMaker Pro change needs testing through the actual client UI — layouts, buttons, scripts with dialogs, portals, conditional formatting, anything the Data API cannot see — and the test should be run by an agent with computer use rather than by hand. Also use when a Codex or Claude computer-use run has returned a "done" or a screenshot and you need to decide whether it actually passed, or when a UI test could not run (wrong file, login failed, approval refused). Requires Ringer and a FileMaker file open in FileMaker Pro on this Mac.
allowed-tools: Bash, Read, Write
---

# fm-ui-test — agent-run UI tests with evidence, not claims

Three seats, never merged: the **builder** (you) writes the instruction, the
**runner** (Codex computer-use, under Ringer) performs it and returns a receipt,
the **verifier** (a fresh model context) reads the receipt and rules. The
runner's "done" is never a pass. A green Ringer check on the runner task means
*the receipt is well-formed*, not that the product works.

## Workflow

1. **Split the assertions by channel.** Persisted values (field contents,
   record counts) are read through the Data API / ExecuteSQL (`fm-dataapi`,
   `fm-odata`, proofkit `execute_filemaker_sql`) — never from pixels when a
   hosted door exists. Rendered state (layout, dialog text, button visibility,
   the `?` overflow marker, portal rows) is the UI runner's job. Local, unhosted
   files have no data door; then the orchestrator seeds and reads ground truth
   itself with the Claude computer-use MCP (`references/tool-matrix.md`).
2. **Seed ground truth before dispatch**, independently of the runner, and
   write it to `truth.json` (`references/receipt-schema.md`). Values the runner
   must read back are decided here, not after.
3. **Write the instruction** from `references/instruction-template.md`. Every
   assertion has an id, a type, an exact expected value, and the evidence that
   proves it. Preconditions state file, layout, mode, record primary key,
   account. Hard rules travel in the spec.
4. **Dispatch through Ringer** with `references/manifest-template.json`:
   runner task check = `scripts/check_receipt.py --truth truth.json`.
   The check fails a BLOCKED receipt on purpose so the blocker is visible;
   a `max_attempts: 1` lane for any step that mutates data.
5. **Verify in a second task** (fresh context, receipt + artifacts only, no
   runner narrative, no code): check = `scripts/check_verdict.py`. Only this
   task's PASS is a product pass.
6. **Reset** before any replay: re-deploy the fixture file (`fm-otto`) or run
   the file's reset script through the Data API. Never let Ringer's retry
   re-run a mutating step against dirty state.

## Outcomes

| Runner outcome | Meaning | Check result |
|---|---|---|
| `PASS-OBSERVED` | ran, every assertion has evidence and matches the runner's read | passes if values match `truth.json` |
| `FAIL` | ran, evidence contradicts an assertion | fails, prints the mismatch |
| `BLOCKED` | could not run: approval refused, window missing, login failed, evidence unreadable | fails, prints `blocker.raw_error` verbatim |

A BLOCKED is not a test failure of the product. Report it as its own line.

## Rules the runs taught (2026-09-12 probe, see tool-matrix)

- Codex computer-use is present in headless `codex exec` but needs a **one-time
  "always" approval for FileMaker Pro given in the interactive Codex CLI**;
  desktop-app approvals are session-scoped and do not carry.
- Codex reads FileMaker through the **accessibility tree** — exact text — and
  screenshots via `app.getScreenshot()` (JPEG; convert with `sips`). The AX
  value can differ from the rendered one (`6.1412E+57` vs `?`): the receipt
  must say which it reports.
- Claude's own computer-use MCP reads FileMaker fine in the background but
  **cannot type into a non-empty field** without foreground control.
- AppleScript `set cell` is refused unless the account has `fmextscriptaccess`.

## Common mistakes (each one seen in a baseline run without this skill)

- "Test the invoice layout" — no assertion ids, no expected values: unverifiable.
- "The dialog is dismissed, so its text can't be checked after the fact" — it
  can: a screenshot at the `dialog-shown` checkpoint plus a verbatim read is
  the evidence, and the verifier compares it. Dropping UI assertions because
  only data assertions have a query is dropping the reason the UI runner exists.
- Reset inside the check, with "if reset fails, don't flip the exit code."
  Reset is step 6, before the next run; a reset that fails is `BLOCKED` for
  every case after it, never a silent pass.
- Letting Ringer's default retry re-run a step that mutates data. Mutating
  lanes get `max_attempts: 1`.
- Letting the runner report a value it inferred from a screenshot as if it
  were read from the tree. Require `source` per observation.
- Treating the runner task's green check as the verdict.
- Retrying a mutating step without a reset.
- One desktop, two GUI workers. Never.
