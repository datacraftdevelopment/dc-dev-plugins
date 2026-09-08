# PM 0.16.0 workflow verification

Verified 2026-09-07 (America/Toronto; UTC run IDs fall on September 8).

The five reviewed fixes are implemented: credential candidate inspection, an explicit Ticket → Build preparation step with isolated environment setup, bound session identities, honest Intent refresh boundaries, and independent delivery acceptance. PM source is 0.16.0; the canonical library build-swarm change is commit `2bb7d66`.

## Executed checks

| Surface | Evidence | Result |
|---|---|---|
| PM repository | `python3 -m unittest discover -s tests -v` | 46 tests passed |
| Canonical build-swarm library | `python3 -m unittest discover -s scripts -p 'test_*.py' -v` | 144 tests passed, no skips |
| Relocated Codex PM package | Plugin validator and packaged `hooks/test-credential-guard.sh` | Manifest valid; 18 hook cases passed |
| Credential policy | `scripts/sync_pm_policy.py --build-swarm <canonical skill> --check` | Byte parity; SHA-256 `16a853d7c02c28f91e1441d775bbdb11e4c33bb68b4f8bb3476793fa6c1dc7f9` |
| Installed PM | Builder installation and app-server `hooks/list` | 0.16.0 installed; hook enabled and trusted; no warnings/errors |

The library timeout regression needs child-process inspection: the first sandbox-only run had one PermissionError. The complete suite passed outside that sandbox, then passed again from the canonical library location. No tests were skipped or weakened to obtain green.

## Live workflow rehearsal

Disposable project: `/private/tmp/pm-workflow-rehearsal`. Runtime: `/private/tmp/pm-rehearsal-runtime`. Delivered artifact: `/private/tmp/pm-workflow-delivered`.

1. Scaffolded the PM template and opened a session through the generated helper. Accepted intent and criteria were committed before implementation. The known, one-session fixture did not require a discovery interview or wayfinder chart.
2. Authored two dependent local tickets, protected executable behavior checks, and a committed setup script that installs a local fixture dependency outside the repository. Preparation preview left ticket bytes unchanged; preparation supplied Check/Owns and normalized `01 — Add greet` to `01`.
3. Ran canonical `loop.py` with Fable, `--wave 1 --max-tasks 2 --setup setup.sh`, protected dependency inputs, and the full baseline suite. Both checks proved behavior-red after successful setup. Both workers passed on their first attempt; the loop independently integrated and checked each patch, committed it, and closed its ticket. Exit 0, elapsed 102 seconds.
4. Codex, which did not implement the CLI, independently executed both accepted criteria against the final local candidate and an exact Git export. All four executions passed: `greet Ada` emitted `Hello, Ada!`; `bye Ada` emitted `Goodbye, Ada!`. Candidate `c0eed0a21610fdbfef6c0eca29ed9446d19b1d00`; file hashes agreed before and after export. The acceptance helper returned ready-for-release before export and shipped after export.
5. Wrote the shared acceptance record and completion link, exercised a bound session re-aim after the loop stopped, closed that exact session, then repeated close. The second close was byte-identical. A final tracker query returned no open tickets; the fixture repository was clean.

Session ID: `4291f200-4521-428d-948d-e0dc565be00d`.

Ringer runs (both one attempt, executed behavior/ownership checks passed):
- `pm-workflow-rehearsal-d228f6-loop-20260908T005329Z-p56154` — ticket 01, implementation commit `606db8d`.
- `pm-workflow-rehearsal-d228f6-loop-20260908T005426Z-p60517` — ticket 02, implementation commit `819d5e8`.

The loop quarantined four discovery suggestions. They were administratively triaged afterward: a duplicate of ticket 02, the expected setup requirement, an already-resolved usage observation, and “Otherwise: none.” This exposes an existing quality issue in discovery-text parsing; quarantine prevented automatic scope expansion. No acceptance criterion was weakened.

## Review dispositions

Fable reviewed the proposal and implementation. Implementation report: `pm-workflow-implementation-review-20260908T002356Z-p34329`. All five confirmed findings were fixed and covered: wrappers/dynamic executables, escaped newlines, pushd, aliases, and missing-interpreter/helper handling. The review incorrectly called the old hook pure Bash; it also depended on Python. The failure handling fix stands independently of that claim.

Fable's library worker passed 141 tests in `pm-workflow-build-fixes-20260908T000713Z-p21108`. Root review preserved that output and added three failing regressions before fixing whitespace filenames, incidental dependency numbers, and setup mutation of existing worker edits. The final library has 144 passing tests.

## Limits and retained evidence

This proves the local Markdown/Python workflow with real model workers and an artifact handoff. It does not prove FileMaker, browser, live API, client delivery, or production deployment. “Shipped” refers only to the disposable rehearsal artifact. The filename guard is a bounded command inspector, not a general shell sandbox or credential-content scanner. Unattended loops do not read personal Intent logs as live control state.

Raw reports, review dispositions, test logs, preparation JSON, acceptance evidence and installed hook status are retained locally in `.review-gate/2026-09-07-pm-workflow-fixes/`. The fixture's `docs/shipped/rehearsal.md` and JSON companion contain the criterion-level outputs, evaluator identities, exact revision and frozen intent hash. Installed skill changes appear in a fresh Codex task.
