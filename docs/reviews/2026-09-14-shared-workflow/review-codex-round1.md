## Summary

Six findings. Reviewed the task diffs and additions, frozen source copies, acceptance/session/review documentation, and generated Codex adapters. All 38 files match their SHA256 values in `files.json`. Supplied logs report 117 plugin tests and 172 loop tests passing. Five targeted runtime tests also passed in scratch: pause during worker execution, pause during integration, timeout remaining aborted, legacy invocation, and protection of the accepted intent.

The findings below were reproduced against scratch copies of the frozen implementation, with unchanged runtime dependencies copied from the permitted canonical context. Reproduction driver: `/private/tmp/dc-review-kn4jm2jm/probe.py`; output: `/private/tmp/dc-review-kn4jm2jm/probe-results.log`. Paths below are relative to `review-surface/`. No source, generated package, or original fixture was modified. No browser, GUI pilot, real model dispatch, installation, or external action was performed; fake-worker/schema results do not establish visual truth or real-engine behavior.

Finding: Access failures during integration still trigger an automatic collision redispatch.

Evidence: `library/skills/agent-operations/build-swarm/scripts/loop.py:943–950` records the classified failure, then unconditionally reopens the first collision. Integration routes any nonzero suite/check exit here (`loop.py:881–886`, `908–911`). Scratch probe `access_failure_collision` used a suite that passes at baseline but prints `Permission denied: fixture access is unavailable` and exits 1 once the candidate file exists. The loop recorded `classification: environment-access`, yet dispatched twice, consumed all four reservations, and returned with `diagnosis: null`, `recovery_used: 0`.

Impact: An opted-in unattended build repeats work despite recorded evidence that access is unavailable. It spends the remaining worker budget on a failure that the accepted recovery contract explicitly excludes, instead of preserving capacity for resolution of the access problem.

Fix: Make the recorded classification control the opted-in collision path. Park environment/access, human-decision, and unknown failures without redispatch. Preserve the existing isolated collision retry only for evidence that qualifies for that path; retain legacy behavior for legacy tickets.

Priority: P1

Confidence: high

Finding: Legacy seam mutations bypass the new diagnosed-recovery gate for autonomy tickets.

Evidence: `library/skills/agent-operations/build-swarm/scripts/seam.py:504–512,526–529` permits `release` or `reopen` to move any parked ticket to ready without checking its autonomy failure, diagnosis, or recovery limit. The public CLI exposes both. In `seam_reopen_access_failure`, an opted-in run parked a ticket for `environment-access`; `seam.py --issues <fixture-issues> reopen 01 --context 'try again'` returned 0. The next opted-in loop committed that change as claim residue and dispatched the ticket again. Output: two dispatches, no diagnosis, and `recovery_used: 0`. Unlike `recovery.py`, this command also does not acquire RepoLock.

Impact: Existing seam callers can blindly retry failed autonomy tickets, including permission-dependent failures that `recovery.py recover` refuses. The diagnosis, permitted recovery cycle, and repo-lock requirements apply only if the caller voluntarily chooses the new command.

Fix: Enforce the parked-autonomy-to-ready transition at the shared seam boundary, covering both `reopen` and non-parking `release`. Require the validated recovery transaction for that transition, while preserving legacy tickets, stale in-progress claim release, and the explicitly allowed collision path. Any separate human override should be explicit rather than indistinguishable from an ordinary release.

Priority: P1

Confidence: high

Finding: Unverified refund residue can replenish an exhausted ticket budget on restart.

Evidence: `library/skills/agent-operations/build-swarm/scripts/loop.py:346–357` permits a reservation's `refund` to change from null to any string during claim-residue reconciliation. `budget.py` only requires a nonempty refund string and an arithmetically matching `used` value; startup does not validate the referenced Ringer record. Probe `unverified_refund_residue` first exhausted the budget with two incomplete fake runs, each recording two attempts. It then changed only the uncommitted Autonomy header: both refunds became `"nonexistent-record"` and `used` became 0. `claim_shaped` returned true; restart committed those bytes and issued a third two-attempt dispatch. There was no completed zero-attempt record. The resulting journal retained the two fictitious refunds and showed `used: 2` after six reported attempts.

Impact: A corrupt or mistakenly edited control header is accepted as an interrupted transaction, silently weakening the four-attempt ceiling. The normal refund API's authoritative-zero-record check is bypassed by restart reconciliation.

Fix: Validate every newly introduced refund during residue reconciliation against the authoritative completed record, exact wave/task identity, and integer zero attempts, including refunds on newly appended reservations. If that proof is missing or untrusted, refuse the residue or conservatively retain the reservation; a refund identifier alone must not authorize a counter decrease.

Priority: P1

Confidence: high

Finding: A supported custom kit can silently omit the agreement from every worker brief.

Evidence: `library/skills/agent-operations/build-swarm/scripts/loop.py:604–621` checks for the worker preamble and rejects unknown placeholders, but does not require `CONSTRAINTS_AND_RULINGS` in the spec. The agreement is supplied only through that optional substitution. Probe `kit_missing_policy` used the normal CLI with `--agreement` and a kit whose spec was `You are the single implementation worker for this task\n{{TICKET_BODY}}`. The loop dispatched and closed the ticket successfully. The generated spec was exactly the preamble plus `create src/x.py`; it contained no agreement, scope, technical choices, frontend checkpoint, or protected-path instructions.

Impact: An orchestrator using a shortened/custom kit receives a successful build while workers and their internal retries never receive the accepted policy. Integration path checks still operate, but cannot make the omitted scope and frontend decision instructions available to the worker.

Fix: Inject the accepted agreement and mandatory constraints into the final worker spec independently of kit placeholders, or fail preflight when an opted-in kit cannot carry them. Verify the final packet before reserving attempts or dispatching.

Priority: P1

Confidence: high

Finding: Acceptance uses a weaker agreement parser that admits malformed policy and can fall back to legacy shipping.

Evidence: `plugins/pm/scripts/acceptance.py:29–39,142–149` recognizes only the exact heading and validates only `policy` and the type of `approved`. Probe `missing_agreement_fields` supplied just `{"policy":"dc-autonomy-v1","approved":true}` with otherwise matching evidence; the CLI returned 0 and `shipped`, although the runtime rejects the missing scope/actions/build fields. Probe `malformed_heading_legacy` supplied `## execution agreement` containing invalid JSON, with no evidence-requirements block or channel entries. The CLI again returned 0 and `shipped`: the malformed heading was treated as absence. The canonical runtime detects that heading variant and rejects it. Both probes supplied the correct intent digest and matching criteria.

Impact: The same malformed accepted intent is rejected by the build runtime but admitted by the delivery validator. A heading typo can also disable the requirement for channel evidence and allow an unqualified shipped result, contrary to the documented fail-closed contract.

Fix: Use equivalent strict agreement-section detection and complete schema validation at both boundaries. Distinguish genuine absence from a malformed/ambiguous attempted agreement; reject unknown/missing fields and invalid limits before computing acceptance. Keep operation-specific action requirements separate so review-only agreements remain possible.

Priority: P2

Confidence: high

Finding: Supplied evidence outside the required-channel list bypasses candidate and implementer checks.

Evidence: `plugins/pm/scripts/acceptance.py:58–67` checks all supplied channel names/container types, but validates evaluator, revision, and evidence fields only inside `for name in required`. Probe `extra_channel_wrong_identity` added a `ui` channel to criterion A1, whose required channel is `automated`, in both phases. That extra channel claimed `status: pass`, `evaluator: worker-1` (the implementer), and `revision: older-build` (candidate is `abc123`). The real CLI returned 0 and `shipped`, claiming revision/identity consistency. No exception was supplied.

Impact: A delivery record can include self-evaluated, stale evidence and still receive an unqualified shipped verdict. This occurs when an evaluator supplies additional channels beyond the accepted minimum, such as supplemental screenshots, and contradicts the documented guarantee that identity violations cannot be excepted.

Fix: Validate schema and identity for every supplied channel before checking required-channel completeness. Alternatively, reject channels not declared for that criterion. Keep the required list responsible for which evidence must be present, rather than which supplied evidence is checked for consistency.

Priority: P2

Confidence: high
