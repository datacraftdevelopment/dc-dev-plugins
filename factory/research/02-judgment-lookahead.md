# Judgment lookahead: prep the next decision while the current work runs

> The design behind `experiments/01-runway`. Written 2026-10-05.

## The goal, in Joe's words

> If we could prep the next piece that needs judgment and that's ready for that, so that it's on the list and ready to go. The current one is working.

So there are two lanes running at once:

- **AFK lane:** tickets that don't need Joe run one after another, with no prompt from him.
- **Judgment lane:** the next ticket that does need Joe is prepared *before* the AFK lane reaches it, so when he looks, there's a packet waiting and all he has to say is "go."

The loop never waits on Joe. If the only thing left needs him, it stops and says so.

## Ticket states

Everything stays in pm's existing local-markdown tracker. Runway adds one header line, `Gate:`.

```
Gate: auto       (default) the loop may run it unattended
Gate: human      needs Joe's go before any work
Gate: approved   Joe said go; the loop runs it like an auto ticket
```

The flow for a gated ticket:

```
ready + Gate: human
   │  its blockers are all AFK work (or already done)
   ▼
prep agent (read-only) writes "## Decision packet" into the ticket
   ▼
Status: needs-human, Waiting on: Joe, notification sent
   │  Joe: runway go 03 "use greet()"
   ▼
Status: ready, Gate: approved  ──► AFK lane picks it up when unblocked
```

For an AFK ticket:

```
ready + unblocked ──► claimed ──► agent in a worktree on runway/<ticket>
   ──► check command ──pass──► merged into runway/integration, resolved
                     └─fail──► one retry with the failure output
                                 └─fail again──► needs-human with the log
```

An agent that hits an unplanned decision writes `RUNWAY_QUESTION.md` and stops; the ticket parks as `needs-human` with the question. That's the reactive path PM already has. The lookahead is the new part.

## "Prep ahead" precisely

A gated ticket gets prepped when **every open blocker is AFK work the loop can finish on its own**. That means:

- A gated ticket blocked only by AFK tickets is prepped at the start, while those AFK tickets are still running. By the time they finish, the packet has been sitting there.
- A gated ticket blocked by another gated ticket waits; prepping it now would mean deciding on top of an undecided decision.

In the offline demo, ticket 03 ("Choose the public API name", blocked by 01) was prepped first, before 01 had even started. The loop then ran 01, 02 and 05, stopped with only 03 waiting, and after `go 03` it ran 03 and then 04, which depended on it.

## The decision packet

The prep agent is told not to change files, and writes exactly these sections:

- **Decision needed:** one sentence answerable with go, no, or a one-word choice
- **Options:** two or three, each with its consequence, recommendation marked
- **What the agent will do on "go":** plan, files likely touched, how it's checked
- **Risks / one-way doors**
- **Context Joe needs:** at most five bullets

This mirrors the `ask_decision` card shape used in Projects and PM's `fast-grill` idea that Joe should only see taste, one-way doors and splits.

## Where Joe answers

The first version is deliberately low-tech: `runway status` lists what's waiting, and `runway go NN` / `runway no NN "reason"` answers. A `notify_cmd` (a macOS notification, a Pushover call, anything) can ping him when a packet lands. Later options, in rough order of effort:

1. Answer by editing the ticket (`Gate: approved`) from any editor; the loop picks it up next tick.
2. Show the queue on `board.html` (pm's board already renders `needs-human` first).
3. Mirror packets to a phone surface: a Projects thread, a GitHub issue comment, or a Basecamp to-do, with "go" as the reply.

## What triggers the loop

Version 1: Joe runs `runway loop`. That already removes the per-ticket touches. Version 2 (experiment 03) runs `runway tick` from `launchd`/cron every few minutes on the Mac mini, or from a file watcher on `.scratch/`, so a `go` is picked up without Joe starting anything. That's the point where it becomes a factory by Matt's definition.

## What to measure

- **Touches per ticket:** how many times Joe had to act, by ticket type. The target is zero for AFK tickets and one (the go) for gated ones.
- **Packet lead time:** how long a packet was ready before Joe looked. Positive means the lookahead worked.
- **Parked failures:** how often AFK tickets bounced to `needs-human`, and why. This is the retro input: each one is a candidate check, a better ticket, or a gate that should have been declared.
- **Tokens per accepted ticket**, compared with an ordinary PM session and with Hermes.
