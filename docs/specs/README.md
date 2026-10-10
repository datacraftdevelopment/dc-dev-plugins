# Specs

One file per spec: what `/to-spec` writes, after the plan has been talked
through. This file is the spec's source of truth. Its GitHub issue (labelled
`spec`) is the tracker entry: it starts with a `Spec:` line pointing here and
carries a copy of the text, and its sub-issues are the build tickets.

Each ticket names its spec in a `Spec: docs/specs/<slug>.md` header line, so a
Runway worker reads the spec from its own checkout instead of the tracker.
The spec file reaches `main` before its tickets are labelled `ready-for-agent`.

A spec changes here first; then re-paste the text into its issue.

Not the same as `docs/intent/`: an intent is the earlier discovery note
(problem, outcome, acceptance), written before anything is planned. Planning
notes and grilling ledgers stay with the planning conversation; whatever in
them binds the build goes into the spec.
