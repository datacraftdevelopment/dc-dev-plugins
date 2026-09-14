## Summary

Three P2 findings remain. This is a review report, not an implementation delivery. Source corrections below are recommendations only. Reproductions use disposable scratch repositories and records. All 45 frozen source copies match `files.json` SHA256 values.

The seven original cases now pass their targeted regressions: integration access failures park without collision redispatch; direct parked-ticket claim/reopen/release is refused; invented refund records are rejected; short custom kits fail before grants; previously reported malformed agreement forms block; supplemental scalar identity/revision violations block; and pause during lint consumes no reservations. The section-title false-positive regression passes. Raw parked-to-ready residue is refused, legitimate interrupted recovery still lands, and recovery.py enforces both `recovery_cycles: 0` and exhausted `max_worker_attempts: 2` during residue landing. The findings below are separately reproduced residual variants.

Fresh executed evidence in `/private/tmp/dc-readonly-review-hbh29sno/`: `runtime-targeted.log` reports **48 tests OK**; `plugin-targeted.log` reports **44 tests OK**, including template/runtime parity and the section-title regression. Commands used `RINGER_NO_SELF_UPDATE=1` and `RINGER_NO_CATALOG_REFRESH=1`. Supplied `loop-tests.log` and `plugins-tests.log` separately report 192 runtime and 140 plugin tests passing; those full-suite counts are supplied evidence, not fresh full-suite executions in this review.

Checks cover legacy modes, restart/collision/internal-retry reservations, exact-zero refunds, protected accepted intent and worker constraints, recovery locks, pause acknowledgement/draining/no later dispatch, and abort states. Session ownership, repeat-grilling rules, multimodal procedures and frontend checkpoints were inspected. Generated PM acceptance/parser bytes and the Ringer review reference match frozen source; generated Ringer skill text matches the host converter. Paths in findings are relative to `review-surface/` unless absolute.

Limits: fake-worker and schema evidence cannot establish GUI truth or model compliance. The denied GUI pilot remains unexecuted; this review involved no browser access, real model dispatch, installation or external delivery. The restart worker's outer delivery check timed out and is not counted as PASS.

Finding: Parked failure evidence can be replaced through residue reconciliation before invoking diagnosed recovery.

Evidence: `library/skills/agent-operations/build-swarm/scripts/loop.py:377–394` requires unchanged failure/diagnosis only when the working status leaves `needs-human`. Keeping that status unchanged bypasses those checks; the remaining checks allow an appended Failure section and a corresponding replacement of the header's latest failure. Reproduction: `/private/tmp/dc-readonly-review-hbh29sno/park-probe.py`, output `/private/tmp/dc-readonly-review-hbh29sno/park-probe.log`. The disposable scratch fixture ran the actual loop with a fake worker and parked for `environment-access`; `recovery.py recover` initially returned 1. In that scratch fixture, without another worker or manual commit, the reproduction retained the parked status and reservations, appended a schema-valid `AssertionError` Failure for the same run ID, and updated the latest-failure header. `claim_shaped(..., accepted_limits)` returned True. Loop restart committed the edit, with the ticket still parked but classified `behavior`. The normal diagnosis/recover CLI then returned 0 and the next loop dispatched again. Output: `dispatches 2 used 4 recovery_used 1`. The original worker record still reported permission denial.

Impact: A raw, uncommitted control edit can replace the disqualifying failure while retaining the parked status, have the loop legitimize it as an interrupted transaction, and make an otherwise forbidden access-failure retry eligible. This requires a control edit; an ordinary untouched parked ticket remains protected. The four-attempt ceiling still holds, but the failure-classification recovery restriction does not survive this two-stage restart path.

Fix: Recommended source correction for the orchestrator: For a committed parked autonomy ticket, validate permitted residue mutations even when its status stays parked. Preserve its failure identity/history unless a supported transaction can actually produce a new failure; diagnosis residue may update the diagnosis of that existing failure. Reject the demonstrated appended replacement failure before either startup or recovery commits it, while retaining real in-progress failure residue and legitimate diagnosis/recovery transactions.

Priority: P2

Confidence: high

Finding: Whitespace inside a policy-section label still silently disables acceptance enforcement.

Evidence: Both copies of `agreement_contract.py:146–149` use `re.escape(heading)` with a literal single space, so `## Execution  agreement` and `## Evidence  requirements` produce no attempted-heading match and return None. `/private/tmp/dc-readonly-review-hbh29sno/acceptance-probe.py` and `/private/tmp/dc-readonly-review-hbh29sno/acceptance-probe.log` reproduce the public acceptance CLI: an approved agreement under the doubled-space heading, with no requirements block or channel entries, returns exit 0 / `shipped`; the runtime loader rejects that same agreement with `expected exactly one ## Execution agreement heading`. Separately, a legacy intent containing a doubled-space Evidence requirements heading and its actual `ui`/`state` JSON mapping also returns `shipped` when the record omits the mapping and all channel entries. Both records carry the correct intent digest and criteria.

Impact: An ordinary spacing typo in a Markdown heading can hide an attempted agreement or declared evidence requirements from the delivery validator. It certifies delivery without the corresponding mandatory channels instead of reporting the malformed section. The existing case/level/decoration regressions do not exercise this input.

Fix: Recommended source correction for the orchestrator: Recognize horizontal-whitespace variants between the section-label words as attempted headings, then retain the exact canonical-heading validation so they block. Apply this in the shared helper and vendored copy for both labels. Preserve the current prefix restriction that allows unrelated section titles to mention these phrases.

Priority: P2

Confidence: high

Finding: Non-scalar evaluator identities bypass the new channel self-evaluation check.

Evidence: `plugins/pm/scripts/acceptance.py:55–58` checks that channel identity fields are truthy, then compares the evaluator directly with the implementer without validating their types. `/private/tmp/dc-readonly-review-hbh29sno/acceptance-probe.py` sets the required UI channel evaluator to `["worker-1"]` in both phases of the supplied otherwise-valid fixture, whose implementer is `"worker-1"`. The real CLI returns exit 0 / `shipped`, claiming identity consistency. Replacing that evaluator with `{"id":"worker-1"}` produces the same result. No exception is supplied. Output is preserved in `/private/tmp/dc-readonly-review-hbh29sno/acceptance-probe.log`.

Impact: A record producer that supplies evaluator identities as a list or object can pass builder-generated UI evidence through the independence gate. The record is structurally invalid for scalar identity comparison, yet receives an unqualified shipped verdict. This is a schema/identity-validation failure, independent of whether the evidence media are authentic.

Fix: Recommended source correction for the orchestrator: Validate implementer and evaluator identities as nonempty scalar strings before comparing them, including every supplied channel. Reject containers and other invalid identity types rather than treating unequal representations as independent evaluators. Add CLI cases for the demonstrated list/object identities.

Priority: P2

Confidence: high
