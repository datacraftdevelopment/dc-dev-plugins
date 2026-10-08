# Field notes: one orchestrator session, several build lanes

> **Direction corrected by Joe, 2026-09-14:** the objective is completed work
> without blockers or supervision, with lean orchestrator context (roughly
> 150k–200k tokens). Six to eight sessions across machines caused a Mini crash,
> manual reopening and recovery; shipping the work did not establish a net gain.
> Autonomous ticket work should use subagents, not additional interactive
> sessions. Automate the usual one-or-two-ticket → stepping-away → fresh-session
> rhythm. One active orchestrator is the default; at most three sessions across
> both machines, with extras only for independent work when explicitly warranted.
> The first beta tests a single chain of three successive orchestrators.
> [Accepted succession implementation](pm-019-session-succession.md) supersedes
> the concurrency-first recommendations below; retain these observations as evidence.

Author: Joe (with Opus). Status: **field notes, still collecting**. This is not an intent yet;
it becomes one once the pattern has run for a few days. Started: 2026-09-14.
Pilot: a client repo (Next.js + Supabase, main-only, auto-deploys on push).

Joe's aim: run 2–3 Claude Code sessions at once, each building its own piece on its own
branch, plus one session that doesn't build and acts as the orchestrator. Eventually this
becomes a standard pm pattern.

```
                 ┌──────────────────────────────┐
     Joe ───────▶│  ORCHESTRATOR (main tree)    │  assigns lanes · merges · deploys
                 │  owns tracker/changelog/     │  prod-verifies · client face
                 │  client face · lane board    │
                 └──────┬──────────┬─────────┬──┘
          spawn_task    │          │         │    send_message / disk checks
                 ┌──────▼───┐ ┌────▼─────┐ ┌─▼────────┐
                 │ DB lane  │ │ lane A   │ │ lane B   │   each: own worktree + branch,
                 │ :3001    │ │ :3002    │ │ :3003    │   own dev-server port, commits
                 │ may DDL  │ │ code only│ │ code only│   on its branch, "ready to merge"
                 └──────────┘ └──────────┘ └──────────┘
                        └── one shared database, one prod ──┘
```

---

## How we implemented it (2026-09-14)

1. **Starting point.** One session (CM2, a commission-payout feature) was already running
   in a worktree when the idea came up. The repo's rule since May was main-only, because
   branches used to get orphaned.
2. **Lane picking.** The orchestrator read the project tracker, sorted open tasks into
   *writes to the DB* vs *code only*, and grouped the code-only work into clusters that don't
   touch the same files. It also listed what has to wait while a lane holds a hot file (the
   listing-actions file, the commission file, listing detail).
3. **Rules written into the project tracker**, under Development Workflow, with a
   **lane board** at the top of Current (lane, branch, work, port, DB rights, status).
   The six rules:
   1. **One database.** A branch isolates code, not data. One lane at a time holds the
      **DB lane**; it alone runs DDL, migrations, backfills and scripts. Migrations stay
      **additive** until merge so deployed `main` keeps working. Prod DML still waits on
      Joe. Other lanes write to the sandbox tenant through the app UI only.
   2. **Test logins are shared.** No lane rotates the test-user passwords (the rotate script
      rewrites `.env.local` in one tree and breaks every other session's login).
   3. **Ports.** One dev-server config per lane (3001/3002/3003).
   4. **Shared files belong to the orchestrator.** Lanes don't edit the tracker, the
      changelog, CLAUDE.md or the client tracker, don't push to main and don't deploy.
      A lane's notes go in its own `_pm/sessions/` file.
   5. **Lanes don't share files.** The orchestrator screens for file overlap before
      assigning.
   6. **Merge or kill the same day.** A lane ends green (build + lint + tests, both Codex
      gates, a local browser check) with a "ready to merge" report; the orchestrator rebases,
      merges, deploys and prod-verifies.
4. **Rules committed to local `main` before spawning**, so the new worktrees inherit them
   and the extra port config.
5. **Lanes spawned with `spawn_task`.** Each lane shows up as a chip, and one click starts
   a session in a fresh worktree. The prompts are self-contained (template below).
6. **The already-running lane was retrofitted** with one `send_message` note: you hold the
   DB lane, here are the rules, and tell me if you've already broken one.
7. **Check-ins** use `list_sessions` / `get_session` / `list_events`, plus reading each
   worktree's disk directly (`git status`, which files exist, which env files are present).

### Lane prompt template (as used)

```
You are lane <X> in a parallel-session setup for <repo>. An orchestrator session on
`main` (<main path>) assigns lanes, merges and deploys. You build one task cluster on your
own branch in this worktree, and nothing outside it.

First: read the rules — <tracker> → Development Workflow → Parallel sessions (commit <sha>).
- You are / are NOT the DB lane. <what that allows>
- Never run <secret-rotation scripts>.
- Don't edit <orchestrator-owned files>. Don't push to main; don't deploy. Commit on your branch.
- Other lanes own <files>; stay off them.

Setup (the worktree has no env files or deps):
1. cp <main>/app/.env <main>/app/.env.local <worktree>/app/
2. <install command>
3. Dev server: <port config name>; log in as <test user> (<sandbox tenant>).

Your work: <task ids + one paragraph each, scope edges, what is out of scope>.

Process: plan → cross-review gate → build → green → gate the code → browser check on your
port → commit on your branch.

Finish with a "ready to merge" report: branch, commits, pasted verification output,
screenshots, anything deferred, client-facing wording for the orchestrator.
```

---

## Sessions today

| Session | Worktree / branch | Work | Port | Started |
|---|---|---|---|---|
| Orchestrator | main tree | lane board, rules, checks, merges | — | ~09:00 |
| DB lane | `compassionate-faraday-8c9264` | CM2 payout numbers: new table + FK + RPC, 9-row prod backfill | 3001 | 09:04 (started before the rules existed) |
| Lane A | `brave-austin-04dfd1` | closed estates: hide from lists + "include closed" toggle, portal login gated on estate status | 3002 | ~09:19 |
| Lane B | `cool-shamir-df4a38` | honest reset-email toast, roll-label rotation, guest tags without price | 3003 | ~09:19 |

---

## Field log

- **09:05.** The first worktree session started **with no env files and no `node_modules`**.
  Fresh worktrees get tracked files only, so it couldn't build, run the dev server or reach
  the DB. Every lane needs a bootstrap step.
- **Conflicting instructions, resolved by a better rule.** Joe first said "DB writes stay on
  main", then "leave the CM2 lane alone". Both hold if the rule becomes **"one DB lane at a
  time, additive migrations until merge"**. The real insight: *a branch isolates code, not
  data*. Every worktree talks to the same database and the same prod, so the database is a
  single lock, not a per-branch thing.
- **Hidden shared state (beyond git)** found while planning: test-user password rotation
  (rewrites `.env.local` in one tree), dev-server ports, the tracker/changelog/client-tracker
  files, prod deploys. None of these show up as merge conflicts; they fail at runtime or in
  the client's eyes.
- **Committing the rules before spawning** was needed so new worktrees inherit them. Worth
  confirming whether a spawned worktree branches from local `HEAD` or `origin/main` (today:
  local `HEAD`, since both new lanes sat at the rules commit `4804886`).
- **`send_message` to a busy session reported "undelivered"** after its 20 s window, yet the
  target flipped to running within seconds. There's no read receipt, so the orchestrator
  can't confirm a lane got the rules.
- **`list_events` on another session shows only tool-call names**, not the text. The
  orchestrator can't see a lane's reasoning. **Disk is the reliable status channel:** git
  status, new files, env files present, session notes.
- **The orchestrator reviewed the DB lane's migration straight from its worktree** (read the
  SQL file before any commit) and confirmed it was additive. That's a useful checkpoint the
  orchestrator can run without interrupting the lane.
- **Four orphaned worktree folders** from earlier sessions were found under
  `.claude/worktrees/`. They're missing from `git worktree list`, and each holds a copy of
  `app/.env`. That's secret sprawl plus clutter; lanes need a cleanup step when they end.
- **Orphans cleaned (Joe's go).** There were actually five, not four (one had no env copy).
  Their git admin entries pointed at the repo's **old Dropbox locations**, which were deleted in
  the move to `~/Agentic-Mini`, so `git status` was useless inside them. Safety check that
  worked without git: diff each orphan against main, git-blob-hash every differing file, and
  ask the repo `cat-file --batch-check` which blobs it has never seen. That left one
  orphan with four never-committed files, an early off-list item-type fix that the tenant
  value-lists feature (R1) later superseded, plus generated `next-env.d.ts`. Gate trails were
  all already in main. Moved the five folders to the macOS Trash (`/usr/bin/trash`) rather
  than deleting them: ~12 GB, reversible until the Trash is emptied. **Plugin idea #5's
  orphan check should be exactly this blob test.**
- **pm's credential-guard hook blocks piped and looped git commands**, so a cross-worktree
  status sweep takes one literal `git -C <path>` call per tree. That's friction for the
  orchestrator; a sanctioned sweep script would remove it.
- **~09:30. Report-in channel added (idea #8, done by hand).** Each lane got a message: use
  `send_message` to the orchestrator's session id when the gate passes its plan (files it
  will touch), when it's blocked, before a DB write (DB lane), and when it's ready to merge;
  and keep a `## Lane status` block at the top of its session file. Delivery: one
  "delivered", two "queued" (busy mid-turn; they're held and run when the turn clears).
  "Queued" is a real state, not a failure. Earlier "undelivered" was the 20 s timeout
  on a session that picked the message up late.
- **Decision (Joe): the session-vs-subagent split is the rule.** If Joe needs to be involved →
  session lane; if the orchestrator can run it end to end → subagent. Written into the pilot
  tracker as lane rule 8.
- **Joe's clicks are part of the cost.** Spawned lanes need a click to start, and each lane can
  stop on permission prompts. With three lanes plus the orchestrator, Joe's attention is the
  real limit, not the model's.
- **~12:50. The Mac ran out of memory; Joe restarted and brought all three lanes back.** 16 GB
  machine. After the restart, before the lanes had restarted their dev servers: 51% free,
  with the Claude CLI sessions at ~2.4 GB, the Claude app ~1.2 GB, other node ~1.4 GB and
  Chrome ~0.7 GB. The likely culprits before the crash were three Next.js dev servers plus
  staggered `npm run build` / vitest / Codex gates in three trees at once. **RAM is a second
  hard limit next to Joe's attention.** Rule added: one dev server at a time where possible;
  a lane stops its dev server when its browser check is done and before `npm run build`.
- **Post-restart disk sweep (3.5 h in): no commits in any lane, and everything is still
  uncommitted work in the trees.** That's a restart risk: a crash mid-edit loses nothing on
  disk, but the lanes' in-flight reasoning is gone. Recommendation: lanes commit WIP on their
  branch at each green checkpoint (they squash or keep, either way it merges).
- **The status blocks were uneven.** The DB lane's was excellent (state, DB writes done, what's
  owed at deploy, a new ticket for the tracker). Lane B's was stale (said "plan gate in flight"
  while its tree held finished edits and tests). Lane A had no session file at all. The
  file-based mailbox only works if updating it is enforced (hook or ritual), not requested.
- **The sweep caught a real file clash:** lane A is editing `middleware.ts`, and the DB lane
  planned a comment there. Messaged the DB lane to skip it. Neither lane would have seen
  it; only the orchestrator's cross-tree view does. The DB lane's message came back
  "undelivered" again (20 s window), as it did the first time.
- **The DB lane ran its migration and prod backfill with Joe's yes** at ~09:27, just before my
  "message me before a DB write" rule reached it. Now owed at deploy: re-run the backfill,
  then a gap query must return 0. That's an orchestrator merge step the lane handed over in its
  status block, which is exactly how it should work.

- **~13:05. First lane report-in: lane B, "ready to merge" by `send_message`.** The
  report was exactly the requested shape: branch, commits, files, what changed, fresh
  verification output, samples, deferred items, and Basecamp lines in plain English. The
  push model worked; I didn't have to poll. Orchestrator merge took ~5 minutes: diff-stat
  scope check (no other lane's or orchestrator's files), a read of the core change, `merge
  --no-ff` into local main, then vitest + build + lint re-run on the merged tree.
- **A gap the pattern hides: lanes can't log in.** Lane B's safety rules forbid typing a
  password, even the sandbox test user's, so its "browser check" became Node-rendered PDFs
  and PNGs plus a 2-minute click script for Joe. The orchestrator is bound the same way.
  The *visual* verification step in the pilot's SOP therefore always lands on Joe.
  Recommendation: a login path that uses no password (a dev-only session-minting route or
  a pre-minted cookie file written by the rotate script), or accept Joe's click check as
  part of merge. Either way, the lane prompt shouldn't promise a browser check it can't run.

- **The lane's close-out landed after the merge.** Lane B committed its session close
  (Intent vs outcome, learnings) *after* "ready to merge", so the branch diverged from the
  merge and I cherry-picked it (`8f9d9c9`). It flagged this itself, and that saved the
  close-out from being lost when the worktree gets cleaned. **Order fix for the plugin:** a lane
  writes its close first and says "ready to merge" last, so one merge picks up everything.
  The orchestrator's cleanup step checks `main...branch` is empty before removing a
  worktree.
- **Memory cause confirmed:** lane B's first full `npm run build` died with **exit 137**
  (killed, out of memory) while three lanes ran. The rerun under rule 9 was clean.
- **Lanes surface library candidates but can't write them** (they're outside their files).
  The orchestrator is the natural place to route "learned" items into `_library`.

- **~13:40. Lane B shipped end to end by the orchestrator:** Joe's local click check →
  push → Vercel Ready, with the deploy log checked to confirm it built *the pushed commit*
  (`Commit: cb408ea`) → prod smoke (`/login` 200, auth redirect) → Basecamp (one ticket to
  Shipped, Status comments on two partly-shipped clusters, *What shipped* entry verified by
  content) → TASKS/changelog/index → push → worktree to Trash, branch + tag deleted after a
  two-dot diff showed main held everything. About 15 minutes of orchestrator time for a lane
  that built for ~4 hours. **The orchestrator's merge-and-ship checklist is the most
  reusable piece so far; it's `pm:merge-lane` (idea #6) almost verbatim.**
- **Crash audit, done after the ship:** `origin/main` hadn't moved since the morning (so nothing
  pushed was lost), every lane's work was still on disk, and the DB lane's DB writes were
  recorded in its status block. The restart cost time, not work. The WIP-commit rule
  (rule 9) is what keeps that true.
- **Lane A is still silent at ~4 h:** no commits, no session file, no reply to three messages,
  though it's running and its tree has many edits. The pattern has no escalation for a lane
  that doesn't report in. Idea: after N hours with no status-block update, the
  orchestrator flags it to Joe instead of sending more messages.

## How it went (fill in at the end of the day)

**2026-09-14, first run: three lanes, all shipped the same day.**

| | Lane B (small fixes) | Lane A (closed estates) | DB lane (CM2) |
|---|---|---|---|
| Started → ready to merge | ~09:19 → ~13:05 | ~09:19 → ~13:45 | 09:04 → ~13:50 |
| Shipped to prod | ~13:30 (`cb408ea`) | ~14:00 (`0558735`) | ~14:00 (`0558735`) |
| Size | 28 files, +708 | 28 files, +1,250 | 31 files, +6,351 (incl. gate trail + samples) |
| New tests | 3 test files | 48 cases | 1 test file |

**Merge order:** B, then A, then CM2. Pushes: two (B alone, then A + CM2 together).
**Conflicts:** one shared file (`middleware.ts`, lane A's gate plus CM2's comment), which
git auto-merged. It was caught ahead of time by the orchestrator's cross-tree sweep,
not by either lane.
**Re-verified on the integrated tree** after every merge: vitest 367 → 415 → 448, build,
lint (81 → 79).
**Orchestrator time per ship:** ~15 min (scope check, a read of the risky code, merge, green
on main, Joe's click check, push, deploy-log commit check, prod smoke, Basecamp,
TASKS/changelog, worktree cleanup).
**Serial estimate:** three ~4 h builds would have been a two-day run; this was one
morning plus a crash.

**What broke or nearly broke**
- **The Mac ran out of memory** (16 GB, three lanes). One lane's build died with exit 137, and Joe
  restarted. No work was lost, because everything was on disk; rule 9 came out of it.
- **A lane went dark for ~4 h** because it was sitting on an `AskUserQuestion` to Joe, and every
  orchestrator message queued behind it. Nobody knew until `list_events` showed the
  question as its last action. **Idea: when a lane asks Joe something, it also pings the
  orchestrator, so the ask doesn't sit unseen in a background window.**
- **Its Codex code gate died mid-run with the restart**; the retry, on Joe's call, went through.
  A separate gotcha: the gate reviews the *uncommitted* diff, so "commit first, then gate"
  hands it nothing to review.
- **Lanes can't log in** (no typing passwords), so Joe's click check stood in for every visual
  verification, on local, not prod. Prod checks were limited to the deploy-log commit,
  public pages and signed-out redirects.
- **Close-outs landing after the merge**: fine when the lane committed before archiving, or
  when the orchestrator merged the final tip. One stale-looking branch tip (`eceb283`) turned
  out to be in main already; `merge-base --is-ancestor` is the check to run before deleting a
  branch.

**Did the rules hold?** Mostly. The DB lane was the only DB writer; its migration was
additive and its prod backfill had Joe's yes. No lane rotated passwords, pushed or
deployed. No lane touched the tracker, changelog or Basecamp; the orchestrator did all
of that. Rule 5 (no shared files) had one miss (the `middleware.ts` comment), which was
harmless. Rule 7 (report in) worked for two lanes out of three; lane A was blocked on
Joe, not on the rule.

**Top three for the plugin, in order:**
1. `pm:merge-lane`, the ship checklist above.
2. `lane-setup` + a memory-aware `lanes status`.
3. A report-in channel that isn't `send_message`: status blocks enforced by a hook, plus an
   "I asked Joe something" ping.

---

## Ideas and recommendations for the plugin

Roughly in the order they'd pay off.

1. **`pm:orchestrate` (session-open ritual for the orchestrator).** It reads the tracker,
   proposes 2–3 lanes, runs a **file-overlap screen** (reuse build-swarm's parallel-safety
   screen), picks the DB-lane holder, writes the lane board and spawns lanes from the
   template. It pairs with `whats-next`; it doesn't replace it.
2. **Lane config per project**, e.g. `.pm/lanes.json`: env files to copy, install command,
   port range, test-user rotation commands to forbid, orchestrator-owned paths, DB-lane
   commands (migrations, scripts). The skills and hooks read this, so nothing project-specific
   is hard-coded.
3. **`lane-setup` script.** It copies the declared git-ignored env files into the worktree,
   installs deps, claims a free port and registers the lane on the board. Today every lane
   did this by hand from its prompt.
4. **Deterministic backing via hooks**, the way credential-guard backs the secret rule:
   - block Edit/Write on orchestrator-owned paths when the cwd is a lane worktree;
   - block migration/DDL/script commands unless this worktree holds the DB-lane lock
     (a lock file in the main repo naming the holder);
   - block the secret-rotation scripts from any worktree;
   - block `git push origin main` and `vercel --prod` from lanes.
5. **`lanes status` sweep.** For each worktree it shows the branch, commits ahead, dirty files,
   whether env files are present, the last commit time and any "ready to merge" marker. It
   flags orphaned worktree folders and prunes them only with confirmation. It lives inside
   credential-guard's rules (or gets an allowlist entry).
6. **`pm:merge-lane` (orchestrator ritual).** Rebase on main → rerun green on the
   integrated tree → merge → deploy → prod-verify → fold the lane's session notes into the
   tracker, changelog and client face → remove the worktree and its env copies.
7. **Split `stepping-away` by role.** A lane's close writes only its session file plus
   the ready-to-merge report. The orchestrator's close does the tracker, changelog and
   client-face work for every lane that merged.
8. **A file-based mailbox instead of relying on `send_message`.** Each lane keeps a
   `## Lane status` block at the top of its session file (state · blocked on · ready to
   merge y/n). The orchestrator reads the files; `send_message` is used only to nudge.
   Lanes could also `send_message` the orchestrator when they're ready to merge.
9. **Position it next to build-swarm, not instead of it.** build-swarm runs unattended
   Ringer workers per ticket, minutes-scale, patches applied by the orchestrator. Lanes are
   interactive sessions Joe can talk to, hours-scale, committed branches. The principle is the
   same (the orchestrator integrates; workers never touch main), and a lane could run
   build-swarm inside itself.
10. **Default cap of 3 lanes**, one of them the DB lane. The limits are Joe's attention
    (permission prompts, questions) **and the machine's RAM**: 16 GB ran out with three lanes.
    The lane config should declare a memory budget. `lane-setup` / `lanes status` report
    `memory_pressure`, a lane stops its dev server after its browser check, and heavy steps
    (`npm run build`, full vitest, Codex gates) check free memory first or take a shared
    "heavy step" token so only one tree builds at a time.
11. **WIP commits at green checkpoints** inside a lane, so a crash or restart costs reasoning,
    not work, and the orchestrator's sweep can see progress as commits rather than dirty files.

## Session delegation vs subagent delegation (Joe's question, 2026-09-14)

| | **Session lanes** (`spawn_task`, separate sessions) | **Subagents** (Agent tool, optionally `isolation: worktree`) |
|---|---|---|
| Joe in the loop | can drop in, redirect, answer questions, approve in context | none until the report comes back; a question just comes back as its output |
| Orchestrator's view | thin: disk, tool names, unreliable `send_message` | direct: the report lands in context, and it can continue them with `SendMessage` |
| Tool surface | full (browser pane, MCP, skills, own subagents) | narrower, depends on the agent type; browser verification is awkward |
| Lifetime | outlives the orchestrator, hours-scale | dies with the orchestrator, minutes-scale |
| Context | own full window; orchestrator stays lean | results pile up in the orchestrator's window |
| Rule enforcement | prompt + CLAUDE.md + hooks; can drift | tool restrictions per agent type; tight spec |
| Joe's cost | a click to start each lane, prompts spread across windows | approvals funnel into one window |

**Pattern that falls out: two tiers, chosen by task shape.**
- *Will Joe need to be in the loop before it's done* (taste, a prod OK, a DB write, a
  browser look)? → **session lane**.
- *Can a check tell whether it's done* (review, investigation, audit, a ticket with a
  committed check)? → **subagent / build-swarm worker**, run by whichever session owns the work.
- So: Joe ↔ orchestrator ↔ lane sessions ↔ subagents. Each lane is itself an orchestrator
  of its own subagents; this project's CLAUDE.md "AgentZero" pattern already does that
  inside a session.

## Open questions

- Should the orchestrator ever build, or stay strictly hands-off? (Today: hands-off, but it
  did read and review a lane's SQL.)
- Where should the lane board live: the project tracker (visible, but it's an edit to a shared
  file) or a pm-owned file like `_pm/lanes.md`?
- What happens when a code-only lane finds it needs a schema change mid-flight: hand it to
  the DB lane, or swap which lane holds the DB?
- Should lanes push their branches (backup plus preview deploys), or stay local until merge?
- Do lanes run their own Codex gates (today: yes, per lane), or does the orchestrator gate once
  on the integrated tree?

## Review notes: Opus, from the YoJoe session (2026-09-14)

A second data point from the same day: the YoJoe Wayfinder map, where the tickets are planning
work rather than code. Joe's goal there is for the agent to move through the map on its own and
bring him in only where his answer changes the work.

### What happened

- One session was grilling ticket 05 when Joe asked for ticket 04 in parallel. The 04 lane was
  spawned with `spawn_task` from that working session; there was no dedicated orchestrator. Two
  sessions ran without trouble because a grill is Joe-paced: the session sits idle while Joe
  reads. → On the open question: an orchestrator can carry one Joe-paced ticket itself, but not
  a build.
- **Where Joe's time went on 05:** four replies over three rounds, every one "all as
  recommended". That covered 7 taste calls, 1 user challenge and 3 seat splits: 19 decisions,
  none reversed. The round trips held the grill up, not Joe's thinking.
- **The spawning session is told when a spawned session ends.** A "you'll be notified here when
  it ends" notice arrived when Joe clicked the chip. That's a completion channel alongside disk
  and `send_message`. Worth checking whether it carries the lane's last message.
- **A claim made in a lane's worktree doesn't show on main.** 04 still read `open` in main's
  tracker while its lane was working on it, so a second orchestrator pass could have handed it
  out again. → Claim on main *before* spawning and commit it, the same way the rules were.
- **Planning lanes collide on shared append-only files, not code:** the map's *Decisions so far*
  list and `CONTEXT.md`. Both lanes append in the same place, so git will report a conflict every
  time. → Either set `merge=union` on those files in `.gitattributes`, or apply rule 4: the lane
  writes only its ticket's Answer, and the orchestrator adds the map line and glossary terms at
  merge.
- **The orphaned-worktree finding repeated.** YoJoe had a worktree whose git record pointed at
  the old Dropbox path ("prunable"). It was checked with `git archive` of its branch plus
  `diff -r`, and only a gitignored token differed. Same Dropbox-move cause as the client pilot. The blob
  test above is the more general check.

### What would let YoJoe run itself (ranked)

1. **Use the Execution agreement that already exists.** A `dc-autonomy-v1` block in the intent
   does three things: it turns off draft-approval loops for session bookkeeping, authorizes local
   commits and Ringer review, and lets technical seat splits settle under `technical_choices`
   after one investigation. YoJoe's intent has no agreement, so every close and commit waited on
   Joe. Friction: an approved agreement requires an `## Evidence requirements` block, and the
   template's fields are build-shaped (`test_targets`, `build`). A planning map needs a lighter
   variant or explicit guidance.
2. **Provisional grill.** Run every round on the recommended taste answers, marked provisional,
   and show Joe one ledger per ticket for a single OK. On 05 that turns 4 round trips into 1. The
   cost when Joe disagrees is re-grilling the branches behind that answer. One-way doors and user
   challenges still stop the grill and wait for him.
3. **Route by ticket shape**, the doc's two tiers applied to a map:
   - research → Ringer worker, unattended (01–03 already ran this way);
   - grilling → provisional fast grill, one OK from Joe;
   - prototype → a real Joe checkpoint, because his reaction *is* the answer.
4. **Chain tickets in one session.** After resolving a ticket, run `checkpoint` and take the next
   frontier ticket instead of closing. Close only when Joe is needed or everything left on the
   frontier waits on him.
5. **Lanes only when the frontier is wide and mixed.** YoJoe's frontier today is 04 + 07. Once 04
   resolves it opens to 07, 08, 10, 12 and 14. Pair a Joe-heavy ticket with Joe-light ones; two
   grills at once just means Joe answers two streams of questions.

### On the ideas list

- **#1 `pm:orchestrate`:** on a Wayfinder map the blocking edges already screen dependencies, and
  the frontier is the lane list. The overlap left to screen is the shared planning files above.
- **#7 split `stepping-away`:** agreed. It covers the map line too; a lane shouldn't write it.
- **#8 mailbox:** add the spawn-end notification as a third channel.

### Adopted on YoJoe (later the same day)

- **Levers 1 and 2 are live.** The YoJoe brief now carries an approved `dc-autonomy-v1`
  agreement (YoJoe `ad1125c`): planning-only scope, actions `local-edit`, `local-test`,
  `local-commit`, `ringer-review`, six technical-choice areas, and `check_map.py` as its test
  target. The map's Notes add Joe's **provisional grill** rule. pm's own validator accepts the
  shape. The build runtime refuses the agreement by design, because it has no `ringer-build`.
- **Friction found while drafting.** The agreement requires a `build` block even when
  `ringer-build` isn't granted (set to the minimums). Approval requires `## Evidence
  requirements` for every acceptance ID, which commits ship-time evidence while the map is still
  planning. And fast grill has no provisional mode in pm, so it lives as a map-level instruction.
  If it works on the next grilling ticket, it's a candidate for pm `fast-grill` itself.
- **The 04 lane reached `main` without an orchestrator merge step.** Its resolve commit (`20c5ddc`)
  and a merge of `main` into its branch (`3764e56`) are both on `main` now. Who landed them isn't
  recorded anywhere the orchestrator can see. Its worktree (`fervent-margulis-c61c9b`) is still registered,
  detached, alongside another lane worktree (`keen-heyrovsky-1184ed`). That's the end-of-lane
  cleanup gap in the field log, reproduced.

## Pointers

- Pilot rules and lane board: the client pilot's `docs/TASKS.md` → Development Workflow → *Parallel
  sessions*, commit `4804886`.
- Related: `pm/WORKFLOW.md` (build-swarm waves, parallel-safety screen), `pm-011`
  (one file per session).
