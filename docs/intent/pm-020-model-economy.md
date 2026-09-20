# PM model economy

Status: accepted and implemented; amended 2026-09-20 by
[pm-021](pm-021-orchestrated-runs.md)
Date: 2026-09-15
Source: Joe's direction in the Hermes / software-factory discussion

## Problem

Using Astra and Fable for ordinary orchestration and implementation consumes the
available account capacity too quickly. That shortens working runs and increases
Joe's involvement, which works against the software-factory goal: more accepted
work completed over longer periods with less human intervention.

## Accepted direction

- Ordinary interactive Codex sessions use Sol.
- Ordinary interactive Claude Code sessions use Opus.
- Astra and Fable run only through Ringer as bounded review seats.
- Ordinary implementation goes to Sol, Opus, or a cheaper locally proven worker
  with an executable contract.
- Executable checks provide continuous verification. Astra/Fable review is
  conditional on a named uncertainty, material integration/release risk, or an
  accepted evidence requirement.
- One focused cross-vendor reviewer is enough for an ordinary challenge. Use the
  Astra + Fable panel only when independent panel coverage matters.
- Review packets contain the accepted intent, exact diff/revision, relevant
  evidence and unresolved question rather than full conversational history.

## Amendment, 2026-09-20 (pm-021)

Astra or Fable may hold the lead seat of an orchestrated run, from a fresh
session on a context budget and as a manager-only seat. Everything else above
stands: they are never implementation workers, and review still goes through
Ringer. Measured cause: in both field runs the orchestrator's own context, not
its model tier, was the larger cost.

## Acceptance

- PM's workflow names Sol and Opus as the ordinary interactive session tier.
- Every PM path that invokes Astra or Fable routes it through Ringer as review
  work rather than an interactive orchestrator or routine implementation worker.
- Session succession preserves the ordinary tier.
- Orchestration routes work by local task-type evidence and executable checks.
- The generated Codex PM package preserves the same model boundary and its
  host-specific Fable grill adaptation.
- Tests fail if the source or generated package loses these rules.

## Measure

Track account capacity consumed per accepted outcome alongside first-try results,
retries, Joe's interruptions and recovery minutes. A lower-tier route that needs
repeated rescue may cost more than it saves; local Ringer evidence decides future
adjustments.
