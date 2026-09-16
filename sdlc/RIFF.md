# SDLC riff — closing the right-hand side of the loop

**Status:** riffing, not decided. 2026-09-03.
**Source:** Joe's chat about his working cycle + https://rcc-adt-course.vercel.app/bonus-sdlc

---

## What already exists (checked, not assumed)

Two of the three things Joe described are already built and doctrinally settled.

**The cross-review cycle is done.** `cross-review-gate` (library skill, `_Core/library/skills/agent-operations/cross-review-gate`) is exactly the "two models, adversarial, consensus applies" pattern:

- Seat 1 `engine: codex` — cross-vendor detection.
- Seat 2 `engine: claude` (Sonnet default; escalate to Fable when the boundary touches live data) — fresh-context detection.
- Consensus rule (Joe's direction, 2026-07-28): **both seats + verified → Agree, applies under standing consent.** Sole-finder → Hold/discuss. Risk tail always stops for a human regardless of vote count.
- Dispatch: Ringer panel where installed, `codex-companion.mjs` otherwise. Offer at the boundary, dispatch on the yes — never auto-fire.

**The gate schedule is already written** — `pm/WORKFLOW.md` § Gate schedule names the same two boundaries Joe named, plus one he didn't:

| Boundary | Default | Framing |
|---|---|---|
| Intent accepted | optional | pre-mortem: "assume this shipped and the client wasn't happy" |
| **Plan finalized** | **yes** | ← Joe's gate #1 |
| **Chunk of code green** | **yes** | ← Joe's gate #2 |

So gates 1 and 2 aren't missing. They're doctrine.

---

## The actual hole

`pm/WORKFLOW.md`'s stage table:

| Stage | Artifact | Owned by |
|---|---|---|
| Verify | test output pasted; review findings | verify-before-done · code-review · cross-review-gate |
| **Ship** | **merge / deploy** | **—** |

That em-dash is the whole conversation. Nothing in the stack owns:

1. **Exercising the real running thing** — drive the local app in a browser against the intent, not just run its tests. `verify-before-done` is a *disposition* ("never claim without evidence") — it deliberately doesn't say **what** to run. Good rule; wrong altitude for "did the feature actually work when a human clicked it."
2. **Deploy** — no step, no gate, no rule. (The course page's rule is the right one: *Claude never touches production; a human applies.*)
3. **Post-deploy proof** — the same checks re-run against prod. Currently zero doctrine.
4. **A terminating artifact.** The chain runs intent → spec → tickets → diffs → *nothing*. There is no shipped record. The course page's own framing is the diagnosis: trust moved **"from the author to the record"** — and this record stops one stage short of the thing being trusted.

`docs/intent/`'s template (Problem · Proposed outcome · Affected users · Constraints · Open questions · Size call) has **no acceptance section**. That is the root cause of #1–#4: nothing is ever written down that says *how we'd know this worked*, so nothing can be re-run to prove it did.

---

## The idea worth chasing

**Write the acceptance checks once, at intent time. Run them three times.**

```
Discover ──> Acceptance block lands in docs/intent/<slug>.md
                     │
     Build           │  (the same checks, verbatim)
                     ▼
  1. LOCAL      run against the dev server / local file   → evidence
  2. PRE-SHIP   cross-review-gate on green chunk          → findings
  ─── human gate: reads evidence + findings, approves ───
  3. PROD       human deploys; re-run the same checks     → evidence
                     │
                     ▼
            docs/shipped/<slug>.md   ← the chain terminates
```

That's what turns "I can trust it" from a feeling into a mechanism: the same named checks, run at three points, with output pasted at each. Not new tests — the *acceptance criteria the intent already implied but never wrote down*.

**Landing spot for the record:** `docs/shipped/<slug>.md`, not `_pm/`. It's shared trust record, not a personal log — the one rule holds.

### Provisional skill shape

One skill, working name `ship-gate` (or `prove-it`). It owns Verify→Ship→confirm and nothing else:

1. Read the intent's Acceptance block. If there isn't one, **that's the finding** — write it now, with the user, before anything else.
2. Name the exercise for *this* stack. Stack-agnostic by design: browser-drive a web app; FM Lens screenshot + script probe for FileMaker; curl for an API; CLI invocation for a tool. The skill says *exercise the real thing*, never *use Playwright*.
3. Run local. Paste output/screenshots.
4. Offer `cross-review-gate` (existing skill, existing consensus rule — don't reimplement).
5. **Stop.** Human deploys. Claude does not touch production.
6. Re-run the same checks against prod. Paste output.
7. Write `docs/shipped/<slug>.md`: intent link, acceptance checks, three evidence blocks, review findings + dispositions, who approved, deployed at.

### Small change with outsized leverage

Add an **Acceptance** section to `pm/skills/discovery/intent-template.md`. One heading. It's what makes step 1 possible and it costs nothing at discovery time — "how would we know this worked?" is a shape question, which is exactly what discovery is for.

---

## New plugin, or pm?

**Recommendation: pm, not a new plugin.** `pm/WORKFLOW.md` is already the SDLC document of record and already carries the stage table and gate schedule. A second plugin forks the stage vocabulary across two homes and guarantees drift. The gap is ~1 skill + 1 template heading + filling the Ship row — that's a pm point release, not a product.

**The fork actually worth deciding** is different from "which plugin": is this thing

- **(a) Joe's working pipeline** — lives in pm, prescriptive, opinionated, assumes his stack; or
- **(b) a teachable framework** — the RCC course page already teaches a version of it to people who don't have Ringer, Codex, or his skill tree.

(a) and (b) want different artifacts. (b) might be a doc in the library or a course asset, derived from (a) — but it should never be a second plugin that has to be kept in sync.

---

## Open questions

- What does "the same check" mean for FileMaker work, where there's no dev server and prod is a hosted `.fmp12`? (Course page: *"the plumbing differs; the gate structure is identical."* Believable, unproven here.)
- Does the third gate — post-deploy — deserve a cross-review, or is re-running the acceptance checks enough? Suspicion: enough. A review of production is an incident, not a gate.
- Does `docs/shipped/` risk becoming write-only noise? Cheap test: would Joe read one six months later when a client asks "was this ever tested?" If yes, it earns its place.
- Is `verify-before-done` absorbed by this, or does it stay as the always-on disposition beneath it? Leaning: stays. Different altitude, different trigger (a *claim*, not a *stage*).

---

## The split — decided direction (2026-09-03)

**Joe: the working pipeline is the build target; the teachable version stays in mind, not in scope.**

### The repo split already exists — don't invent a third home

| Repo | Marketplace | GitHub | Audience |
|---|---|---|---|
| `_Core/starters/dc-plugins` | `dc-plugins` | `datacraftdevelopment` | Joe |
| `_Core/starters/rcc-plugins` | `rcc-fm` | `FMTrainingTV-AI` | RCC students |

Precedent is set and working: `fm-dc` (personal) → `fm-rcc` (teachable), maintained by **fork-and-sync** — commit log literally reads *"fm-rcc v0.7.0: synced from upstream v0.7.0 @ 4ec1e24"*.

### But do NOT apply that pattern to pm

`fm-dc → fm-rcc` is a **debrand**: same tool, branding stripped, delta is cosmetic, so syncing works.

`pm → teachable-pm` is not that. pm assumes Ringer, an authenticated Codex CLI, Matt Pocock's plugin, the `_Core/library` skills, and Joe's `_pm/` conventions. An RCC student has approximately none of them. A debranded fork of pm is **broken by default** for that audience, and every sync would fight the divergence instead of absorbing it.

**What's genuinely shared between the two is doctrine, not code** — the stage table, the gate schedule, the artifact chain, "a human approves the prod gate." That's prose. It's *already* prose, in two places that don't know about each other: `pm/WORKFLOW.md` and the RCC bonus-SDLC page.

### So: split the document, not the plugin

`pm/WORKFLOW.md` currently welds two layers together. Pull them apart:

- **Layer 1 — the spec.** Stages, gate boundaries, artifact chain, who approves what. Stack-agnostic, teachable, publishable. This is what the RCC page is already a rendering of.
- **Layer 2 — Joe's binding.** How the spec is *executed here*: Ringer's two seats and the consensus rule, `cross-review-gate`, Matt's skill per stage, `_pm/` session rituals, `docs/` vs `_pm/`.

RCC gets Layer 1 + a FileMaker binding. pm keeps Layer 1 + Joe's binding. One canonical spec, two bindings, no fork to sync.

### Consequence: pm gets to stop hedging

If teachability lives elsewhere, pm can be **unapologetically Joe's** — name the tools, assume Ringer, assume Codex, assume Matt's stack, drop the defensive generality. That's a real simplification, not just a permission.

### Build order

1. **Ship-gate work lands in pm first** (Layer 2), built for Joe's stack, proven on real work.
2. **Only then** does the generalized statement get lifted into Layer 1.

Not the reverse. Teaching a stage that hasn't survived a real deploy is how the course page ends up describing something nobody does.

---

## Done 2026-09-03: the layer split

- **`pm/SDLC.md`** (new) — doctrine layer. Stages by artifact, the three gates, the artifact chain, what must be proven and when, the three steering layers, shared-record vs personal-log, and a **"what a binding must supply"** checklist (7 rows) that makes a gap in any binding visible instead of implicit. Names no tool.
- **`pm/WORKFLOW.md`** (rewritten) — Joe's binding. Opens by stating it is *not* generic and assumes Ringer + Codex + Matt's skills. Panel seats, escalation rule, and the consensus rule with their proving-round evidence now live here in full rather than by reference to the library skill.
- **`pm/.claude-plugin/plugin.json`** → 0.12.0.
- Pre-split copy preserved at `sdlc/WORKFLOW-before-split.md`. Twenty content markers from the old file checked present across the two new ones — nothing dropped.

**Ship stays deliberately unbound.** The table's Ship row is an em-dash with a section under it naming exactly what's missing. An unowned row is visible; a vague sentence pretending to own it is not.

---

## Public → private: the case

**Facts, 2026-09-03.**

| Repo | Visibility | Note |
|---|---|---|
| `datacraftdevelopment/dc-plugins` | **PUBLIC** | 0 stars, 0 forks, 0 issues since 2026-07-09. 32 clones / 24 uniques in 14 days — indistinguishable from Joe's own `/plugin marketplace update` traffic across machines. |
| `datacraftdevelopment/desk` | **PRIVATE** | Ringer lives here (`Agent/Ringer/ringer.py`). |
| `FMTrainingTV-AI/rcc-fm` | **PUBLIC** | The teaching channel. Unaffected by anything dc-plugins does. |

**The decisive fact: Ringer is private.** As of the split, `WORKFLOW.md` hard-wires a panel that runs on a tool nobody outside can obtain. A public dc-plugins is now documentation for an unobtainable dependency — which is worse than private, because it advertises a capability it can't deliver.

**The reason worth acting on isn't the one first offered.** "Someone coming after me" isn't happening — zero issues, zero forks, in two months. The real cost of public is subtler: **you write differently when strangers read it.** That quiet pull toward generality is precisely what this session spent an hour removing from `WORKFLOW.md`. Staying public re-applies it every time the file is edited.

**Nothing breaks:**
- RCC students consume `rcc-fm`, a separate public repo in a separate org.
- The `fm-dc → fm-rcc` sync runs on Joe's machine, which has access to both. A private upstream is fine.
- `_pm/` is already gitignored; private lowers the blast radius of a credential slip in the repo whose entire job is stamping client projects (see the `Client/RCC` incident in `Agentic/CLAUDE.md`).

**The one real cost:** a public dc-plugins is a credibility artifact for someone who teaches this — *"here's how I actually work."* But `rcc-fm` plus the course page already serve that audience, and serve it better, because they're built for it.

**The one thing to verify before flipping:** that `/plugin marketplace add datacraftdevelopment/dc-plugins` still resolves on each machine once the repo is private. It clones over git, so an authenticated `gh`/credential helper should carry it — **should**, not verified. Test on the second machine before relying on it.
