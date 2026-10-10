# Specs

One file per spec: what `/to-spec` writes, after the plan has been talked
through. This file is the spec's source of truth. Its GitHub issue (labelled
`spec`) is the tracker entry: it starts with a `Spec:` line pointing here and
carries a copy of the text, and its sub-issues are the build tickets.

Each ticket names its spec in a `Spec: docs/specs/<slug>.md` header line, so a
Runway worker reads the spec from its own checkout instead of the tracker.
The spec file reaches `main` before its tickets are labelled `ready-for-agent`.

A spec changes here first; then re-paste the text into its issue.

Runway puts the text of the ticket's spec file into the worker's prompt (and
prep's), read from the worker's own checkout, so the worker never has to reach
the tracker for it.

Planning notes the spec came from (the plan, a grilling ledger) can sit beside
it as `docs/specs/<slug>.notes.md`. Runway names that file to the worker
without inlining it. This repo is public, so a notes file goes in only when it
is clean (no client names, credentials or NDA material); whatever in the notes
binds the build belongs in the spec itself either way.

Not the same as `docs/intent/`: an intent is the earlier discovery note
(problem, outcome, acceptance), written before anything is planned.
