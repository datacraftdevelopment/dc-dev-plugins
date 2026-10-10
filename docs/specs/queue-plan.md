# Spec: one queue plan for Runway's tick, sign-in check, status and finish

Tracker entry: #46 (tickets #47-#50). Moved here from the issue body on 2026-10-10.

Audit candidate 2 (Runway architecture review, 2026-10-09). The interface was settled with Joe using fast grill: Joe ruled on the taste calls and Astra (gpt-6-astra, through Ringer) ruled on the technical ones. Any ruling can be reversed with a comment on #46.

## Problem

"What happens to this ticket next" is decided in four places: the tick's prep step, the tick's run step, the sign-in check, and status grouping. The tracker half of finish's gate is a fifth. Each place has its own copy of the gate, blocker, claim and harness rules, and they already disagree about what status shows:

- A gated ticket behind another of Joe's decisions shows as "Ready (needs prep)", but the tick never preps it.
- A ready ticket with an unknown harness label shows as "Ready (auto)", but the tick parks it.

## The queue plan (interface)

A pure module beside the engine (`queue_plan`), with no git, tracker, clock or I/O. It has one public function:

`plan(tickets, machine, finish_mode, harness_cfg) -> QueuePlan`

Inputs: every loaded ticket (Runway's or not), this Mac's name, runway.json's `finish` mode, and the harness config (the default plus the profiles). Pause, quiet hours, sign-ins and orphan release stay outside the plan. The plan reads only the ticket interface: id, effort, num, gate, status, claimed_by, blocked_by and harness.

QueuePlan carries:
- **steps**: for each Runway ticket, in tracker order, one **next step** and a short reason. The steps are run, queued, prep, park, waiting, running_here, running_elsewhere, claimed_unknown_owner, blocked and done. A ticket whose status is outside these is left out of the groups.
- **run_now**: the first runnable ticket, or none. This is a candidate, not a promise: pause, machine rules, base sync or a lost claim can still stop it.
- **prep**: every gated ticket the tick should prep this pass.
- **park**: every ready ticket with an unknown harness label, Runway's or not (as today), with the reason.
- **harnesses_needed**: the harness of every run, queued and prep candidate, for the sign-in check.
- **finish**: the **finish verdict**, covering only the tracker half of the gate. It is one of finish, wait (a ticket is claimed), wait (N open under all_done), or off. `finish --force` skips it. Finish's git checks (ahead count, head already reviewed, base-sync-only work) stay in finish.

## Rules pinned (unchanged from today)

- Precedence: a bad harness label parks the ticket first, on any ready ticket, whatever its gate or owner. Next comes terminal, waiting or claimed status, then human lookahead (which ignores claim stamps), then runnable eligibility (owner and blockers).
- Blocker lookups use every loaded ticket, keyed by (effort, num), with stub blockers included. A missing blocker counts as done, and a ticket in a cycle is never lookahead-eligible.
- A gated ticket is prepped only when all its open blockers are auto work the loop can finish on its own.
- One ticket starts per tick, and prep still covers every eligible gated ticket.
- Finish: off wins, an empty queue counts as all done, and an unknown mode behaves like idle.

## How the callers use it

- **Tick**: build the plan, then run the sign-in check on `harnesses_needed`. As today, the check returns before any park or prep. Then do the park and prep pass with today's pause and machine checks, rebuilding the plan from the same loaded list after each park. Then sync_base, reload, build a fresh plan and run `run_now`, keeping the second pass's bad-harness park. The plan is rebuilt only at today's reloads (after orphan release and after sync_base).
- **Status / status --json**: the groups come from the steps. The keys and `version: 1` stay the same; the new fields are additive: a per-ticket `next_step` and `reason`, and top-level `run_now` and `finish`.
  - waiting ← waiting, park
  - running ← running_here, running_elsewhere, claimed_unknown_owner
  - ready_auto ← run, queued
  - ready_prep ← prep
  - blocked ← blocked (including gated tickets behind another decision)
  - done ← done

## Tests

Pure tests run the plan on fake tickets and cover every step and each disagreement above. Focused tick tests pin the ordering: the sign-in check comes before any change, parks happen in order, and the run is picked from the reload after sync_base. Existing behavior assertions stay. Mocks and exact-shape checks change only where the new seam or the additive fields require it.

## Tickets

Sub-issues of #46. All of them wait on #7, which moves the engine into pm.
