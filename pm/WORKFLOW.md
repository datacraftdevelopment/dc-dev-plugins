# WORKFLOW — how Joe works

Joe's binding of [SDLC.md](SDLC.md). One orchestrator owns the outcome and the
user conversation. Autonomous work goes to bounded Ringer subagents. The working
unit is a meaningful outcome ticket; worker assignments are not additional tickets.

## Model economy

Ordinary interactive sessions use **`gpt-5.6-sol` in Codex** and
**`claude-opus-5` in Claude Code**. Those sessions own the user conversation,
technical execution, integration and routine judgment. Session succession keeps
the same ordinary tier when it creates a fresh orchestrator.

**`gpt-6-astra` and `claude-fable-5` are review seats**, invoked **only through
Ringer**. They receive bounded review packets for a named uncertainty, material
integration risk or release decision; they do not become interactive PM sessions
or routine implementation workers. Prefer one cross-vendor seat for a focused
challenge. Use both seats when an applicable cross-review gate or accepted
evidence requirement calls for independent panel coverage.

Executable checks remain the continuous quality layer. A green worker result is
integrated and checked by the ordinary orchestrator; it does not automatically
buy an Astra or Fable pass. Give a review seat the accepted intent, exact
diff/revision, relevant test evidence and the unresolved question. Keep transcripts
and unrelated repository history out of the packet. Judge this routing by
**account capacity consumed per accepted outcome**, alongside user intervention
and recovery cost.

## Default execution path

1. **Read the outcome.** Reuse the user's request, accepted intent and existing
   ticket. Create a ticket only when work needs its own durable outcome, owner,
   dependency or acceptance boundary. A file edit, test, scaffold step or worker
   assignment does not earn a ticket by itself. Direct small requests can be done
   and recorded without manufacturing tickets.
2. **Prepare.** The orchestrator resolves shared interfaces and does necessary
   scaffolding before fan-out. Read `orchestrate` for the worker graph: each node
   has a bounded output, owned files, prerequisite outputs and a check. Keep this
   compact plan under the parent ticket, not in a second tracker.
3. **Dispatch ready work.** Up to **six active subagents**, including any nested
   workers, when independence and resources permit. Six is a ceiling, not a
   target. Choose the least costly locally proven model that can satisfy each
   worker's executable contract; ordinary implementation starts with Sol, Opus,
   or a cheaper proven worker rather than an Astra/Fable review seat. Run ready
   branches concurrently; release dependent nodes only after their inputs are
   verified and integrated. Shared data, credentials, ports and heavy checks
   count as dependencies even when files do not overlap.
4. **Integrate and verify.** The orchestrator reads short reports, checks patches
   against scope, integrates in dependency order and verifies the combined
   outcome. Choose checks that could catch the actual failure; run required
   project checks. Keep full builds and other heavy integration checks out of
   simultaneous worker runs. `verify-before-done` owns evidence before claims.
5. **Record and continue.** Put completion evidence and essential decisions on
   the original ticket. Park genuine human decisions there with `Waiting on:` and
   `Status: needs-human`. Present them together in the orchestrator conversation;
   take other independent work while they wait. Stop when none remains.

`orchestrate` is the execution entrypoint; it uses the existing Ringer transport.
For a frontier of real tickets with committed checks, `build-swarm` can execute
the same graph in waves. Use its documented preparation, ownership and recovery
controls. Explicitly select a screened wave width up to six; its CLI's default
remains one. Never create tiny tickets just to satisfy the loop's input format.

Manual session rotation remains normal: `stepping-away` → fresh session →
`whats-next`. The handoff carries outcome, evidence, essential decisions and the
next ready work. An explicit request to continue through fresh sessions may use
the **experimental** `session-succession` skill; installation does not enable it.

## Add process only to resolve an uncertainty

| Situation | Tool to reach for |
|---|---|
| Outcome or scope is unclear | `discovery` to shape the missing intent. |
| Several unresolved decisions depend on each other | `/wayfinder` and a focused grill. Duration across sessions alone does not require a map. |
| A design needs a written contract | `/to-spec`; reuse an existing accepted spec. |
| Independently useful outcomes need separate ownership or ordering | `/to-tickets`; worker steps stay inside their parent ticket. |
| A technical decision needs an independent challenge | `fast-grill`; name the disputed assumption before buying a round. |
| A concrete correctness, integration or release risk remains after checks | `/code-review` or `cross-review-gate`, scoped to that uncertainty. |
| A bug's cause is unknown | `/diagnosing-bugs`; reproduce before fixing. |
| The user needs to react to something tangible | `/prototype`; their reaction is the useful checkpoint. |

No automatic panel at every plan or green chunk. State the uncertainty, why the
existing evidence doesn't settle it, and the smallest useful review. Another
round requires a material change, unresolved finding, or explicit project/user
requirement. Once invoked, `cross-review-gate` still owns its panel, consent,
finding disposition and freeze rules. Required checks and accepted evidence
channels remain required; "lean" is not permission to skip them.

The expensive-seat boundary applies inside every review path: Astra and Fable
run as Ringer workers with a declared task, check, artifact and usage record.
Never switch the interactive orchestrator to either reviewer for a review. A
reviewer does not continue into fixes; the ordinary session or a separately
bounded implementation worker applies accepted findings and reruns checks.

**For PM-bound work, this conditional schedule overrides generic stage-trigger
text in imported skills**, including `cross-review-gate`'s "plan finalized" /
"chunk passes tests" triggers and `/implement`'s blanket review step. Those are
not reasons to initiate an extra review here. A specific project/user review
requirement still applies. The external skill supplies mechanics only after this
schedule selects a review; no global library policy is changed for non-PM work.

When a technical grilling seat is justified, Claude-led work uses the **Astra seat** (`engine: codex, model: gpt-6-astra`, kit `_Core/Ringer/local/templates/grill-review/`).
The Codex edition adapts that seat to Fable. `fast-grill` owns mechanics. An
explicit map's `Seat: on` remains binding; ordinary technical choices already
covered by the user's authorization don't need another round.

## Authorization and questions

Carry the user's existing scope and permissions forward. Do not ask again just
because a new ticket, skill, worker or session is involved. A direct request can
authorize routine local work and its bookkeeping without a separate agreement.
Ask when the answer changes product intent, scope or an action lacking permission.
Workers return blockers to the orchestrator; they don't open new interactive
sessions or send independent question streams to Joe.

An optional `dc-autonomy-v1` Execution agreement in the accepted intent records
machine-readable grants and budgets for the unattended runtime. Approval is
recorded, never invented: templates stay `approved: false`. Malformed or unknown
agreements grant nothing. The canonical runtime still validates its committed
snapshot and owns its limits; this workflow does not relax that contract. Host
permissions and the user's instructions outrank it. Publishing, production and
client messages need their own applicable authorization.

## Shared record and delivery

`docs/` and the declared tracker hold project truth. `_pm/sessions/` contains
per-session, append-only logs bound by path and Session-ID; it is not another
tracker. Use the existing local `.scratch/` tracker by default, or whichever
tracker the project declares (including an existing `TASKS.md`). New loose asks
go to `docs/intent/inbox.md`, matching existing entries first. Inbox grooming is
optional and never a gate on ready work.

The human-question queue is the tracker entries carrying `Waiting on:` plus
`Status: needs-human`, presented together by the orchestrator. The answer stays
on its ticket; no duplicate questions document. A worker implementation detail
can be noted in its brief/report without creating a ticket. Promote it only if
it becomes a separately useful outcome or durable unresolved dependency.

Closing a ticket proves its contracted work; delivering an intent uses
`ship-acceptance` against the actual candidate/delivered revision. Preserve its
required independent evidence channels and the project's release authorization.
Report blocked, ready-for-release, shipped or released-with-exceptions honestly.
Follow `docs/agents/client-face.md` only when the project has opted into that
interface. Reusable lessons travel to the library only when they would prevent
a future mistake; otherwise the code, ticket and evidence are enough.

## Session shape

- `whats-next`: read a compact handoff and ready outcome; start authorized work.
- `orchestrate`: scaffold, dispatch the ready graph, integrate and verify.
- `checkpoint`: record a consequential change of direction when needed.
- `stepping-away`: close the record, keep a concise next-work handoff and release
  owned disposable resources. Manual fresh sessions remain the default.
- `session-succession`: optional turnover experiment, judged on fewer user
  restarts, interruptions and recovery minutes—not on session count.
