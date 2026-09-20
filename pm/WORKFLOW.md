# WORKFLOW — how Joe works

Joe's binding of [SDLC.md](SDLC.md). The default is one session working one
outcome with Joe in the loop. Orchestration through bounded Ringer subagents is
opt-in; when it runs, one orchestrator owns the outcome and the user
conversation. The working unit is a meaningful outcome ticket; worker
assignments are not additional tickets.

## Model economy

Ordinary interactive sessions use **`gpt-5.6-sol` in Codex** and
**`claude-opus-5` in Claude Code**. Those sessions own the user conversation,
technical execution, integration and routine judgment. Session succession keeps
the same ordinary tier when it creates a fresh orchestrator.

**`gpt-6-astra` and `claude-fable-5` are review seats**, invoked **only through
Ringer**, with one exception: the lead seat of an orchestrated run (below). They
receive bounded review packets for a named uncertainty, material integration
risk or release decision. Outside that exception they do not become interactive
PM sessions, and they are never implementation workers. Prefer one cross-vendor seat for a focused
challenge. Use both seats when an applicable cross-review gate or accepted
evidence requirement calls for independent panel coverage.

Executable checks remain the continuous quality layer. A green worker result is
integrated and checked by the ordinary orchestrator; it does not automatically
buy an Astra or Fable pass. Give a review seat the accepted intent, exact
diff/revision, relevant test evidence and the unresolved question. Keep transcripts
and unrelated repository history out of the packet. Judge this routing by
**account capacity consumed per accepted outcome**, alongside user intervention
and recovery cost.

### Lead seat of an orchestrated run

Joe answers what only he can, then one session runs the implementation stage
through Ringer workers and comes back with one report. Joe chooses that
session's model when he starts it. Opus or Sol may lead any run. Fable (Claude
Code) or Astra (Codex) may lead only under both conditions:

- **Context budget.** The run starts in a fresh session from a written brief
  and stays under the budget in `orchestrate`. Two field runs spent more on the
  orchestrator re-reading its own context than on all the workers.
- **Manager-only.** A review-tier lead is a manager-only seat: it writes briefs, acceptance tests, checks,
  manifests, tracker entries and integration commits. Product code, including
  small fixes, goes to workers.

Standing seat preferences, so an unattended run does not stop to ask:
implementation `claude-opus-5` on the Claude lane and `gpt-5.6-sol` on the Codex
lane; documentation and research the least costly locally proven model, read by
the orchestrator before it is accepted; review the cross-vendor seat. The local
Ringer scoreboard settles anything these don't, and the report states the choice.

An orchestrated run commits each verified chunk to an **integration branch**.
The base branch changes only when Joe merges or replays it. Keep a review-tier
lead only while its measured tokens stay at or below the workers' tokens.

## Default loop

One session, one outcome, Joe in the loop: `whats-next` → do the work in that
session → `stepping-away`. When ready work remains, `stepping-away` offers to
open a fresh session for it. Each session's context ends with the session, which
is what keeps usage flat.

**Sibling sessions for independent tickets.** This is the default way to run
work in parallel, ahead of `orchestrate`'s subagents; the `sibling-sessions`
skill owns the screen, the launch prompt and the merge rule. When two or three
ready tickets have nothing to do with each other, the session may offer to open
each in its own fresh session. Each sibling is an ordinary
session: its own worktree and branch, Joe in the loop, the ticket owned through
to its own merge (rebase on the base branch, green on the rebased tree, merge on
Joe's word). Nobody watches them: the launching session does not poll, wait for
reports or integrate, because that babysitting was the expensive part of the
lane pattern (pm-018, pm-021). Screen first: disjoint files, one database writer
at most, no shared port or dev server. Three at once is the ceiling on a 16 GB
machine, and each one is a window Joe has to answer.

**Orchestration is opt-in.** Use `orchestrate` when Joe asks for it, or when
there is a real batch of independent tickets, each worth an hour or more, and he
will be away. An orchestrator plus lanes plus workers is more model calls at
once: the first week it was the default, weekly usage went 2.6x on doubled calls
(pm-021). Record tickets accepted and tokens used for every orchestrated run.

## Orchestrated execution path

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

`orchestrate` is the entrypoint for that path; it uses the existing Ringer transport.
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

- `whats-next`: read a compact handoff and ready outcome; do the authorized work
  in that session.
- `sibling-sessions`: two or three independent tickets, each in its own ordinary
  session through its own merge; nobody watches the others.
- `orchestrate`: opt-in. Scaffold, dispatch the ready graph, integrate and verify.
- `checkpoint`: record a consequential change of direction when needed.
- `stepping-away`: close the record, keep a concise next-work handoff, release
  owned disposable resources, and offer a fresh session for the next ready work.
- `session-succession`: optional turnover experiment, judged on fewer user
  restarts, interruptions and recovery minutes—not on session count.
