---
name: ship-acceptance
description: Verify a deliverable against its accepted intent and record delivery evidence. Use after implementation verification, when preparing a release, after a human deploys, or when deciding whether an intent is complete. Supports deployed systems and delivered documents or tools; never deploys production.
---

# Ship acceptance

Own the last handoff: accepted intent → independently executed acceptance → delivery record. An implementation ticket can close after its own checks; this procedure decides whether the intent's outcome was delivered.

## 1. Pin what will be checked

Read the accepted `docs/intent/<slug>.md`, the candidate's exact revision (commit or artifact SHA-256), and review dispositions. Copy the Acceptance lines verbatim with stable IDs (assign A1, A2, … in the record for legacy unnumbered lines). Record the intent file's SHA-256. Changed criteria go back to the originator under existing authorization; they are never weakened to fit output. Completion metadata is excluded from this snapshot by saving the accepted intent bytes alongside the record before later adding its completion link.

Create `docs/shipped/` on first write. Use [record-template.md](./record-template.md) for `<slug>.md`; keep the accepted snapshot and `<slug>.json` beside it. Retain prior release evidence when retrying or replacing a candidate: new dated/revision sections or a new record, never overwrite a failed result with a pass.

## 2. Check the local or staging candidate

Give an evaluator who did not implement the candidate the frozen criteria, candidate identity, target, and runnable/manual procedures. For model delegation use the installed Ringer skill with an executed-check contract. Existing user authorization applies; if delegation has not been authorized, prepare the packet and offer it. A human can evaluate manual checks. The worker's own tests are supporting evidence, not this verdict.

Execute every criterion against the actual deliverable. Record per check: ID, pass/fail/not-run, exact revision, environment, evaluator identity, time, and actual output or a captured observation. Check commands and test fixtures must respect the target's permissions; a live-data write needs an explicitly approved fixture/procedure. Missing tools or access produce not-run with a reason, never an inferred pass. Review opinions do not substitute for execution.

## 3. Record readiness; let the human apply production

Failed/missing required local evidence means blocked. All required local checks pass → ready-for-release. The human applies production. Only after the human confirms deployment and the target is known, verify its actual revision and repeat the same criteria. A different revision requires fresh local evidence too.

For nondeployed deliverables, identify the actual delivered bytes and destination/use context; evaluate that artifact after delivery. A test-run copy is labeled a rehearsal, not production. Do not send files or messages to recipients without explicit authorization.

Any explicit human exception keeps the unmet check and reason visible. It can produce **released-with-exceptions**, never an unqualified shipped verdict. An exception cannot invent evidence or replace the candidate identity check.

## 4. Validate and write the shared record

The JSON companion carries `intent` (link), `intent_sha256`, `candidate`, `implementer`, `criteria` (ID → original text), and `local`/optional `delivery`. Each phase has `revision`, `environment`, and `checks`; each check has `id`, `status`, `evidence`, `evaluator`, `at`. Delivery also has `applied_by`; for a document/tool set `kind: artifact`. Exceptions are `{id, phase, approved_by, reason, at}` entries, based on the human's actual instruction.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/acceptance.py" --record docs/shipped/<slug>.json --intent docs/shipped/<slug>-accepted-intent.md
```

The helper validates completeness and revision/identity consistency. It does not authenticate evidence or perform acceptance. Read the underlying output and confirm the criteria mapping matches the saved intent. Record the returned status in Markdown with the evidence, review dispositions and human approval. A partial release remains blocked or released-with-exceptions, with its open scope named.

For `shipped`, add `Completion: shipped · <record link>` to the current intent, after confirming its substantive content still matches the accepted snapshot. For `released-with-exceptions`, add `Completion: released-with-exceptions · <record link>` and name follow-up work; it is visible at session open until the originator accepts that tail. `ready-for-release` and `blocked` leave Completion pending. `whats-next` reads this record before excluding an intent from the frontier.

Done: shared record identifies what was requested, what was actually delivered, what was checked independently, and what remains unproven. Ship is bound by this procedure; stack-specific browser/FileMaker/API access still requires a real proving run on that stack.
