# PM 0.19 review and verification

Date: 2026-09-14. Scope: outcome tickets, one orchestrator, up to six active
subagents in a dependency graph, conditional ceremonies, manual session rotation
and an optional succession beta.

## Fable review

Requested by Joe; executed through Ringer with `claude-fable-5`.
Run: `pm-session-succession-review-panel-20260914T190225Z-p6761`.
The original report is local Ringer evidence at
`~/.ringer/jobs/pm-session-succession-review/work-final/review-claude/report.md`.

Fable found the implementation aligned with the accepted intent and raised two
findings, both addressed after review:

- P2: imported cross-review trigger text could restore automatic panels after
  every green chunk. PM's WORKFLOW now explicitly overrides generic imported
  stage triggers with its conditional schedule. Specific project/user review
  requirements remain binding; non-PM library behavior is unchanged.
- P3: an attempt-scoped succession command with no handoff raised AttributeError.
  The lookup is now null-safe. A regression reproduced the traceback before the
  fix, then passed for created, acknowledge, cancel and not-created commands.

Fable independently ran the then-current 16 succession and two Codex build tests.
The small fixes above were verified locally, not sent through another panel.
The optional build-swarm executor's CLI and implementation were also inspected:
explicit waves are supported after parallel-safety screening, and the accepted
run budget can further restrict PM's ceiling of six.

## Release evidence

- Full unittest discovery: **166 passed** after the fixes.
- Credential-guard shell checks: **18 passed**.
- Generated Codex PM package validation passed; 12 skill entrypoints.
- Claude: **0.19.0**, enabled. All 47 tracked PM files in the installed cache
  match the source bytes.
- Codex: **0.19.0+codex.20260914191241**, enabled. Installed cache matches the
  generated package, and its source fingerprint matches the tracked source and
  builder. The helper matches source; Codex host adaptation is present.
- Both installed helpers ran the boundary smoke check from `/` successfully.
- Whitespace checks passed. Installation used the supported Claude marketplace
  update and the repository's Codex builder; generated caches were not edited.

Open a new Codex task and restart Claude Code to load the new instructions.
Installation was verified on this Mac. No client project was opted into the
succession experiment. Host startup, required clicks, retirement/resource release,
cross-machine load and net user effort remain live beta checks; passing helper
tests does not establish those outcomes.
