---
name: discovery
description: "Clarify missing outcome or scope through a conversational riff, then capture the intent. Use when the user asks to discover or think through an unclear problem. A clear request or accepted ticket goes straight to execution; size or number of sessions alone does not require discovery."
---

# Discovery

The stage before planning. A conversation, not an interview: the user thinks out loud, you think with them, and the two of you find the shape of the thing — what problem, what outcome, who's affected, what's fixed, what's still open. When the shape holds still, you write it down as an **intent** and make a **size call**. That's the whole job. You don't design, you don't plan, you don't build.

Why it exists: Matt Pocock's `/wayfinder` opens with a breadth-first grill because it assumes it starts from nothing. Its grilling is the heaviest part of the stack. Feed it an intent you've already riffed into shape and it has far less to ask. Discovery is the on-ramp; wayfinder and plan mode are the road.

## Posture

- **Riff, don't interrogate.** No one-question-at-a-time, no multiple-choice menus, no five-question budget. Respond to what was said, push back where it's soft, offer a reframe when one is visible, ask the thing you'd actually want to know next. The user leads the pace.
- **Chase shape, not detail.** The failure mode is nailing down implementation before the outcome is agreed. If the conversation drifts into "which table / which library / which endpoint", pull it back up: "that's a planning question — park it under open questions."
- **Say what you think.** Discovery is where a wrong premise is cheapest to kill. If the problem as stated isn't the real problem, or the outcome doesn't fix it, say so in a sentence and keep going.
- **Read before riffing.** If the project has `docs/intent/`, `docs/adr/`, `GLOSSARY.md` (`CONTEXT.md` in older repos), or `_pm/skeleton.md`, read them first — the user shouldn't have to re-explain what the repo already records. Check whether an intent for this already exists; if so, you're updating it, not starting over. Check `docs/intent/inbox.md` too: if the thing being riffed is already a line there, that line is the seed — quote it, and it comes out of the inbox when the intent is written.
- **Don't fake convergence.** "Are we clean on the shape?" is a real question. If the user is still circling, keep riffing. If they've said "let's move on" or the last two exchanges added nothing, it's time to write.

## When the shape holds still — write the intent

One file, committed, in the shared record:

- `docs/intent/<slug>.md` — this is **shared** engineering record (the next stage reads it; a collaborator or client can read it), so it lives in `docs/`, never in `_pm/`.
- Template: [intent-template.md](./intent-template.md). Sections: Problem · Proposed outcome · **Acceptance** · Affected users and systems · Constraints · Open questions · Size call — plus two optional fenced-JSON sections the template documents: **Evidence requirements** (acceptance ID → evidence channels; required once an agreement is approved) and **Execution agreement** (the `dc-autonomy-v1` opt-in; the intent is its only home). Header carries author, status, date, and a source line (what prompted this — a conversation, an article, an incident).
- **The agreement's `approved` field records the user's actual authorization, given in their own words for this scope.** Draft it `false`; flip it only when they approve it, and say so in the session record. Never pre-approve, never carry approval over from another intent, never treat a global preference as opt-in.
- Write it in the user's terms. Open questions are the fog — things you can tell are coming but can't phrase sharply yet. Don't resolve them here; that's what the next stage is for.
- **Acceptance is not optional and not a test plan.** Ask it as a shape question — *"how would we know this worked?"* — and write the answers as observable checks: what you'd do, what should happen. Three or four. They get run twice later (locally, then against production), so write them so they survive being re-read cold. If the user can't answer, the Proposed outcome isn't concrete enough yet — say so and sharpen it rather than writing a vague line. Where nothing automatable can prove a check, name the manual version; where nothing can prove it at all, record that as a known gap.

  Guard against the obvious failure: acceptance is **shape** (an observable outcome), not **detail** (which assertion in which test file). "Uploading a 20 MB file finishes and the row appears in the list" is acceptance. "`test_upload_large` asserts 201" is planning — park it.
- **If the intent came from an inbox line, remove the line** from `docs/intent/inbox.md` in the same commit and cite it in the intent's Source (`Source: inbox 2026-09-12 · client call · "<the line>"`). The inbox is the tier below; an item never lives in two tiers.
- Show it before committing. The user corrects misunderstandings; you commit the intent **on its own** as the first artifact in the chain. (Never batch it with code.)

## The size call — last section of the intent, and the handoff

Count unknowns, not files. Two answers:

- **Fits one session** → no map. Hand off directly: Claude Code plan mode, or `/implement` / `/tdd` for disciplined execution, with the intent as the brief. Record "Size: one session" in the intent.
- **Interdependent unknowns** → `/wayfinder` when a map would resolve them; name
  those unknowns and attach the intent. Use a technical grilling seat only when
  it answers a concrete uncertainty or the user requests it. Known work that
  spans several sessions goes to `orchestrate`; duration alone does not need a
  map. Keep worker assignments under meaningful outcome tickets.

A third case: if the riff reveals the work is trivial (rename, config flip, one-liner), say so and don't write an intent at all. Discovery shouldn't ceremonialize small things any more than it should rush big ones.

## Terminal state

Intent committed, size call made, next stage named. Discovery stops here. If the user keeps talking design, that's fine — but it's the next stage's conversation now, and the appropriate skill owns it. See the plugin's `WORKFLOW.md` for the full stage chain.
