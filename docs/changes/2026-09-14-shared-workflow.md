# Shared Claude Code and Codex workflow — September 2026

This release makes the DataCraft workflow usable from Claude Code and Codex while keeping Joe involved in product planning, important frontend choices and acceptance. Technical investigation and ordinary implementation proceed through AI within the accepted scope. Ringer cross-review and multimodal verification remain central.

## What changed for the person using it

Planning starts with the desired result and the decisions Joe wants to reserve. AI reads the project, recommends an approach and asks only questions that materially affect product direction, scope or consequential commitments. An accepted intent can record a `dc-autonomy-v1` Execution agreement. Installing a plugin does not accept an agreement or authorize new work.

What’s Next now starts work that the user has already named without another selection interview. When there is no selected task, it recommends one or two next steps. Inbox grooming is optional. Checkpoint re-aims the current session without forcing a close-and-reopen cycle. Stepping Away records outcomes and ownership under existing authorization; closing a chat does not pause a process or schedule future work.

Frontend checkpoints remain explicit. AI can investigate technical detail and build within the agreement, while Joe decides reserved visual direction, scope changes and product acceptance. A technical split gets bounded investigation and focused follow-up before it becomes a question for Joe. Ordinary reversible review findings can apply after independent confirmation; consensus never overrides Joe’s direction or host permissions.

## Compatibility and packaging

The earlier compatibility baseline is commit `d7396fc` (`Support shared Claude and Codex plugin updates`). It adds the shared Codex packaging and refresh path. Claude source plugins remain usable directly; generated Codex packages provide host-specific entrypoints and routing.

This release updates PM to 0.18.0, design-dc to 0.2.2 and ui-test to 0.3.0. The refresh also carries the current fm-dc, basecamp-dc, Ringer, dc-workflow and installed Claris source packages into Codex. It includes referenced review resources and excludes untracked files or symlink escapes from the Ringer package. Codex-led technical grilling selects Fable; Claude-led grilling retains Astra. The cross-review panel remains Astra + Fable.

The canonical execution contract is `library/skills/agent-operations/build-swarm/scripts/agreement_contract.py`. PM packages an exact byte copy so both hosts enforce the same shape. `scripts/sync_execution_contract.py --check` detects drift. Runtime approval/action requirements are additional to generic draft/schema validation; a valid unapproved draft is not build authorization.

See [Codex setup and refresh](../codex.md) for supported installation commands. Private local development uses the `dc-dev-plugins` marketplace; it is separate from the public `dc-plugins` marketplace. Refresh does not require publishing private source.

## Runtime behavior

The build loop takes an explicit committed intent through `--agreement`, validates it before dispatch, protects its bytes from workers and includes its scope and constraints in every worker brief. A custom kit that drops mandatory constraints is refused before claims or grants.

Attempt reservations form a durable per-ticket journal. Internal retries, integration collisions, restarts and the permitted diagnosed recovery share the same accepted total, at most four worker attempts. A completed authoritative Ringer record proving exactly zero attempts is the sole refund authority. Missing, duplicate, malformed or invented records cannot replenish the budget.

Only mechanically proven patch-apply conflicts receive the isolated automatic collision retry. Other integration failures park under their actual classification. Diagnosed recovery requires a safe recorded failure, remaining accepted budget and an unused accepted recovery cycle. Public seam operations cannot reopen parked autonomy tickets around that transaction. Startup and recovery reconciliation validate interrupted state against the committed failure, diagnosis and accepted limits; raw status edits and fabricated replacement failures cannot manufacture retry eligibility.

Pause acknowledgement, reservation commit and process launch share the control lock. An acknowledged pre-dispatch pause consumes no grants. Already launched work drains through integration before a clean pause is reported. Crashes, timeouts and failed reconciliation remain aborts. Pause never schedules a future run.

## Multimodal acceptance

Every acceptance criterion declares the channels it needs: automated, UI, state and/or human. The builder, UI runner and fresh verifier have separate roles. UI evidence comes from actual interactions and captures; persisted state is checked independently of what the screen displays.

The acceptance helper validates the agreement, declared criterion mapping, candidate consistency, scalar evaluator identities and every supplied channel, including supplemental channels. Missing or failed required evidence blocks shipment unless a specifically scoped exception is recorded. Identity violations cannot be excused by an exception. Recognized malformed policy labels—including case, level, decoration and whitespace variants—fail closed rather than silently selecting legacy behavior.

Structural validation cannot authenticate a screenshot, a human approval or the actual person behind a supplied identity. The verifier must inspect real evidence. This release’s live localhost UI pilot was denied by the host’s approval review, so no visual correctness or saved-state verification is claimed for that pilot.

## Review and verification

Ringer’s plan review and Astra/Fable implementation reviews identified concrete boundary defects that the broad suites initially missed. Each accepted sole-finder correction received independent confirmation and a behavioral regression. The corrections cover classification/retry routing, public seam bypasses, crash refunds, missing worker constraints, pause timing, agreement parsing, incomplete/supplemental evidence, interrupted recovery limits, failure replacement, heading whitespace and evaluator types.

The review record distinguishes substantive findings from delivery checks: one completed worker’s outer verification exceeded Ringer’s 60-second check timeout, and one Astra report triggered a phrase-based checker on a scratch-reproduction description. Neither is relabeled as a passing Ringer delivery. The final narrow Astra + Fable panel passed delivery: Astra found no issues, and Fable identified a remaining Unicode-spacing variant and cosmetic documentation errors. Astra independently reproduced and corrected that variant in run `20260914T113831Z-p27477` (PASS); the documentation errors were corrected. The final release verification and installation record are recorded below and in the linked audit.

The automated fixtures prove executable boundaries, not universal model compliance with skill prose or live application behavior. The UI pilot remains an explicit verification gap. Pre-existing unrelated library and repository edits are excluded from these commits.


See the [review audit](../reviews/2026-09-14-shared-workflow/README.md) for the original reports and delivery-check distinctions.

## Final release checks

On the final Unicode-corrected source, the lead ran the actual full suites: **200 runtime tests passed in 79.482 seconds** and **149 plugin tests passed in 17.070 seconds**. These runs use the normal test fixtures, including real temporary Git repositories. All nine generated Codex packages passed plugin validation. Canonical and PM contract bytes match SHA-256 `9f41dfc54df2d8971f386a53bd9cb18ebbef4be92e45ef71c19b3d32b0ac7e28`.

Canonical library implementation commit: `f5e569e` (`Enforce scoped build autonomy and preserve review evidence`). The plugin implementation commit contains this release note and the complete review audit. Local installation verification is complete: see the [installation record](2026-09-14-installation/README.md) and [HTML workflow guide](../workflow-guide.html).
