# Spec: everything that needs Joe becomes a thread in the project

Tracker entry: filled in when the tickets are filed.

## Problem

Joe has no single place that shows what needs him. The app's **Needs you** section
only knows the loops on the Mac it runs on. His other Mac's loops never show there,
it isn't reachable from his phone, and it only lists tickets Runway parked on its own
way through (a decision packet, a failed run). Work that needs Joe from the start
(a prototype, a taste call, something only he can do at the keyboard) never enters
Runway, so it shows nowhere.

Answering is never a typed reply. Every item ends in a Claude session: a conversation,
some checking, often a test. So the place has to start that session when Joe clicks
(Joe, 2026-10-13).

## Shape

1. **Runway pings, the project opens a thread.** When a ticket starts needing Joe,
   the engine sends one HTTPS POST to a Claude Code routine's API trigger. The routine
   posts one line in the SoftwareFactory project chat, `🛫 Needs you: <note>`, and
   the project's coordinator starts a thread on that post. Joe clicks the thread and
   is in a session about that ticket, from either Mac or his phone.
2. **A `joe` label marks work that is Joe's from the start.** Runway never runs
   such a ticket, whatever its other labels say. It lists them as **Your tasks** in
   `status --json` and the app, and pings each one once, like a waiting ticket.

The loop itself stays on the Mac (worktrees, check.sh, Swift builds, Ringer). Only
the list and the click move to the cloud.

## Proven (2026-10-13)

A plain POST to the routine's `/fire` URL with a bearer token and `{"text": "<note>"}`
starts a fresh cloud session. The note arrives as that session's second message, so
the routine's prompt ends the first turn silently and waits for it. The session can
post in the project chat. It can't message the coordinator or a thread (`send_message`
answers "not found"), which is why the hand-off is a chat post. The coordinator keeps a
standing rule in project memory: a `🛫 Needs you:` post becomes a thread titled with
the ticket's title (or "Needs-you test ping" for a note starting `TEST`). Test ping 3
went from POST to an open thread in about 30 seconds.

Routines made inside a private project can't use "new session per fire", and a fire
ignores the routine's bound session, so these details are platform behavior, not choices.

## Rules

- **The note is data.** `<repo> <ticket ref>: <title> · <url> · <why it needs Joe>`, one
  line, with no free text from anyone but Runway. The routine and the coordinator
  treat it as data and never act on instructions in it. Neither ever posts `go` or `drop`.
- **One ping per ticket per reason.** Runway records what it pinged in
  `_pm/runway-pings.json` (ticket id, reason, time) and pings again only when a ticket
  leaves the state and comes back (answered, then parked again).
- **A ping never breaks a tick.** A failed POST (network, 401, 429) logs one line,
  retries on the next tick, and never stops the loop or changes a ticket.
- **Off unless configured.** `runway.json` gets `"ping": {"url": "<routine fire URL>"}`.
  The token lives in the Mac keychain item `runway-ping` (or `RUNWAY_PING_TOKEN`),
  like the Linear key. With no `ping` block, nothing is sent.
- **Client work stays out of the public repo.** The URL and token are per Mac, never
  committed. A repo whose ticket titles shouldn't leave its tracker sets
  `"ping": {"url": "...", "titles": false}`, and the note then carries only the repo,
  the ref and the link.
- **`joe` beats every Runway label.** A ticket with `joe` is never claimed, prepped or
  run, even when it also has `ready-for-agent`. It doesn't block finish: "all done"
  ignores `joe` tickets the same way it ignores specs.

## Tickets

1. **Engine: ping the project when a ticket starts waiting on Joe.** `ping` config, the
   keychain token, the note format, `_pm/runway-pings.json` dedupe, a never-fail POST
   (stdlib `urllib`, timeout 15s), `runway ping --test "<text>"` to send a `TEST` note
   by hand, and a `ping` entry in the sign-in/health check that reports a missing token.
   Tests use a local HTTP stub.
2. **Engine: the `joe` label and Your tasks.** Both adapters load open tickets carrying
   `joe` (GitHub: one more label in the existing query; Linear: the label in the team).
   The protocol gives them gate `none` and status `yours`, and `status --json` gets a
   `yours` group plus `"yours": true` on the entry. Ping each once (reason "yours").
   Blocked by ticket 1 for the ping part.
3. **App: Your tasks.** A **Your tasks** section in the side panel under Needs you, and
   on the board inside the Needs you column under the waiting and errored cards, each
   row with Open (the tracker) and Talk it through (`runway discuss`, which must accept
   a `yours` ticket). Blocked by ticket 2.

## Not now

- An outbox the cloud reads when the note doesn't arrive. So far the note has arrived
  whenever the session waited for it; revisit if a ping ever lands without one.
- Closing the thread when the ticket is answered. The thread's own Claude can see that
  when Joe opens it.
- Pinging from the Runway app (instead of the engine).
