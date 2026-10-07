# Software Factory — Research Notes

> Compiled October 5, 2026 as the starting point for a software-factory repo.
> Sources are linked inline. Things not verified first-hand are marked **(unverified)**. The AI tooling space changes weekly, so re-check versions and features before relying on them.

---

## 1. The concept

**Matt Pocock's definition** (AI Coding Dictionary):

> A system of work where **triggers, not humans, start agent sessions**, so more work runs AFK and HITL time is saved for what needs it.

- **AFK** (away from keyboard): agent work that runs without supervision.
- **HITL** (human in the loop): the points where a human decides something.
- **Dark factory**: a factory with no human review before merge. Treat it as experimental; see the lessons section.

The core design question is which decisions stay human and which get automated.

### Common triggers

- An issue is created or labelled (e.g. `ready-for-agent`)
- A cron schedule
- A CI failure or monitoring alert
- A previous agent session finishing (chaining)

### Human touchpoints

- Writing and labelling issues
- Approving implementation plans
- Final review before merge, reserved for one-way-door changes

### Dan Shapiro's Five Levels

The shared vocabulary for how far along a team is.

| Level | Description |
|---|---|
| 0 | Manual coding, occasional AI search |
| 1 | "Spicy autocomplete" |
| 2 | Pair programming with AI (where most people plateau) |
| 3 | AI writes most code; developer manages |
| 4 | Developer acts as PM: writes specs, reviews outcomes |
| 5 | Dark factory: spec in, software out, no human in between |

Source: [The Five Levels](https://danshapiro.spicytakes.org/post/2026-01-23-the-five-levels-from-spicy-autocomplete-to-the-software-factory)

---

## 2. Anatomy of a factory

Paul Iusztin ([O'Reilly, Sept 2026](https://www.oreilly.com/radar/inside-a-software-factory/)) splits the lifecycle into three buckets:

1. **Planning (human-driven):** triage/intake → brainstorm → plan/spec
2. **Execution (agent-driven):** implement → review → CI/CD
3. **Improvement (feedback loop):** monitoring → incident response → back into intake

### Layer map for a build

| Layer | What it does | Options |
|---|---|---|
| **Intake / backlog** | Well-specified, small work items | GitHub Issues + labels, Linear (Symphony), Beads, Spec-Kit, Matt's `to-spec` / `to-tickets` / `triage` skills |
| **Triggers** | Start sessions without a human | GitHub Actions/webhooks, cron, Claude Code **Routines** (cron / GitHub webhook / API) |
| **Isolation** | Agents can't trash each other or the host | Git worktrees, Docker/Podman, microVMs (Vercel, E2B), Sandcastle |
| **Orchestration** | Fan out, sequence, retry, merge | Sandcastle, Symphony spec, Claude Code Dynamic Workflows / Projects threads, Gas Town, Mastra |
| **Quality gates** | Stop slop before merge | 1) automated checks → 2) agent review → 3) human review |
| **Learning loop** | Each failure becomes a permanent check | Matt's "Retro" skill, Every's Compound Engineering |
| **Observability** | Know what ran, what it cost, what broke | Session logs (JSONL), token usage per run, CI dashboards |

---

## 3. Matt Pocock's approach (AI Hero)

### Quality as a system, from the "Fixing the PR Bottleneck" talk (~Sept 26, 2026)

> "Quality is a system property, not an agent capability."

Problem: agents produce PRs faster than humans can review them (the "slop cannon").

Three brakes, cheapest first:

1. **Automated checks**: lint, typecheck, tests. They cost only CPU.
2. **Automated review**: a dedicated reviewer agent in its own context window that enforces your standards. It **commits fixes rather than leaving comments**. Build your own rather than using CodeRabbit or Bugbot, which produce generic false positives.
3. **Human review**: only for high-stakes, one-way-door changes.

**Retro**: turn every human review finding into an automated check so the same mistake can't recur.

Source: [talk summary](https://finance.biggo.com/news/4884c941b185405c)

### Skills ([mattpocock/skills](https://github.com/mattpocock/skills))

Together these form the planning front half of a factory.

- `wayfinder`: plan large chunks of work as decision maps
- `to-spec`: turn a conversation into a spec
- `to-tickets`: break a plan into tracer-bullet tickets
- `triage`: move issues through a state machine (where `ready-for-agent` would come from)
- `implement`: build from a spec with TDD plus code review
- `code-review`: review on two axes (standards, and compliance with the spec)
- Supporting skills: `tdd`, `diagnosing-bugs`, `codebase-design`, `domain-modeling`, `grill-me`, `handoff`

### Sandcastle ([github.com/mattpocock/sandcastle](https://github.com/mattpocock/sandcastle), MIT)

His open-source factory engine: a TypeScript library for running sandboxed coding agents.

```bash
npm install --save-dev @ai-hero/sandcastle
npx @ai-hero/sandcastle init   # scaffolds .sandcastle/ (Dockerfile, prompt.md, env)
```

```ts
const result = await run({
  agent: claudeCode("claude-opus-4-8"),
  sandbox: docker(),
  promptFile: ".sandcastle/prompt.md",
  maxIterations: 5,
});
```

**Key concepts**

- **Agents:** Claude Code, Codex, Pi, Cursor, OpenCode, Copilot
- **Sandboxes:** `docker()`, `podman()`, `vercel()` (microVMs), `noSandbox()`, or custom providers
- **Branch strategies:**
  - `head`: write straight to the working directory
  - `merge-to-head`: temp branch that auto-merges back
  - `branch`: named, persistent branch, for PRs and multi-phase work
- **Loop end:** the agent loops until it emits `<promise>COMPLETE</promise>`, hits `maxIterations`, or is idle for 600s.
- **Prompt files:**
  - `{{PLACEHOLDERS}}` filled from `promptArgs`
  - Shell expansion that runs inside the sandbox, e.g. `` !`gh issue list --label ready-for-agent` ``. This is how agents pick up their own work.
- **Hooks:** `onWorktreeReady` and `onSandboxReady`, on host or sandbox (e.g. `npm install`)
- **`createSandbox()`:** a warm container so implementer and reviewer agents can run back to back
- **Structured output:** Zod-validated JSON extracted from the agent's output
- **Sessions:** resume and fork for Claude Code, Codex and Pi

**Templates**

| Template | What it does |
|---|---|
| `blank` | Minimal skeleton |
| `simple-loop` | Pick an issue, close it, repeat |
| `sequential-reviewer` | Implement, then review, per issue |
| `parallel-planner` | Plan parallelizable issues and run them on separate branches |
| `parallel-planner-with-review` | The same, plus per-branch review before merge |

**Gaps and caveats**

- No built-in scheduler; you supply the triggers.
- Git and text-file native, so it doesn't fit FileMaker's binary files.
- **(unverified)** How Claude Code authenticates inside the container (Max subscription vs API key). Check before planning to run it on the Mac mini.

### Cohort: AI Coding for Real Engineers

- Doors open Oct 26; 30% discount until Nov 2; class starts Nov 9, 2026.
- Ends with building a factory, designing factories as an exercise, then designing your own. Also covers wayfinder, codebase design, automated and human review, DDD, and feedback loops.
- Past price: **$795 USD** (March–April 2026 cohort). At 30% off that would be roughly $555, but that's an extrapolation since new pricing isn't public. The crash-course purchase is credited toward enrollment.
- Past cohorts had a 30-day refund policy and lifetime access to recordings.
- One student review found the depth thin relative to his free content. The factory material is new.

---

## 4. Anthropic's built-in equivalents (Claude Code)

| Factory layer | Anthropic primitive | Notes |
|---|---|---|
| Triggers | **Routines**: cron, GitHub webhooks, API | Announced at Code with Claude, May 2026 |
| Isolation | Cloud sessions, built-in worktrees, **Managed Agents** (hosted sandbox, checkpointing, scoped credentials) | |
| Fan-out | **Dynamic Workflows** (June 1, 2026) | Research preview; much heavier on tokens |
| Coordination | **Projects with threads** (beta Sept 17, 2026) | A coordinator splits up a goal and dispatches threads, each a cloud session on its own branch, with shared memory. Cloud-only for now; local execution "coming very soon." |
| Autonomy | **Auto mode**: a classifier screens actions for destructive operations and prompt injection | |

### Matt's approach vs Anthropic's

- **Matt / Sandcastle:** explicit, deterministic pipeline you can read. Vendor-neutral, runs on your own hardware, you control the cost.
- **Anthropic:** goal-driven and managed. Less wiring, but less control, Claude-only, cloud-first and token-hungry.

### What carries over either way

- The method: small well-specified issues, feedback loops, a ladder of quality gates, retros.
- Skills: they load the same in a Projects thread as in a Sandcastle container.

---

## 5. Lessons — what makes a factory stick

1. **"Loops are only as safe as their verifiability."** (Dex Horthy)
   - He ran a fully automated factory from July to November 2025. Within three months the codebase had rotted, and one bug took weeks to dig out.
   - Tests catch short-term breakage, not long-term architectural decay.
   - His replacement: about an hour of human architecture work up front, then small reviewed PRs.
   - [Talk](https://www.youtube.com/watch?v=Ib5GBkD555M) · [summary](https://finance.biggo.com/news/15099f5634f5ab9a)
2. **Humans own planning and architecture.** Every serious source keeps this human.
3. **Plan carefully, execute cheaply.** A good plan lets cheaper models execute without wandering. (Iusztin)
4. **Don't automate the whole pipeline on day one.** Automate your single worst bottleneck first, and keep individual commands alongside any end-to-end mode. (Iusztin's first attempt, Squid, became unmanageable.)
5. **Context is the ceiling.** Agents can only find solutions as good as the context layer they're given (docs, domain model, CONTEXT.md).
6. **Every human correction becomes a check.** (Retro / Compound Engineering)
7. **Keep review separate from implementation.** Use different context windows, and have the reviewer commit fixes.
8. **Watch "specification debt."** Specs rot just like code. (Roelants)
9. **A dark factory is still unproven.** "No-review operation should remain experimental." (Roelants report)
10. **Budget tokens explicitly.** Parallel agents burn plans fast; track usage per run.

---

## 6. Reference implementations and case studies

- **[Sandcastle](https://github.com/mattpocock/sandcastle)**: TypeScript, sandboxed, five templates. The most practical starting point.
- **[OpenAI Symphony](https://www.infoq.com/news/2026/05/openai-symphony-agents/)**: a SPEC.md, not a product.
  - Uses Linear as the control plane and keeps one agent on every active ticket.
  - Restarts agents that stall; agents can file new issues, but humans approve them.
  - Reference implementation is in Elixir.
- **[Mastra software-factory tutorial](https://mastra.ai/blog/software-factory)** (July 2026): a full TypeScript build with six agents plus monitoring and drift-detection loops.
- **[StrongDM factory](https://rywalker.com/research/strongdm-factory)**: three engineers, no human-written or human-reviewed code.
  - Code is checked against test scenarios stored outside the codebase, judged by an LLM ("satisfaction testing").
  - A "Digital Twin Universe" of simulated Okta, Jira and Slack runs thousands of scenarios an hour.
  - Open-sourced Attractor, an agent published as a spec.
- **[OpenAI's internal factory](https://newsletter.pragmaticengineer.com/p/openai-software-factory)** (Pragmatic Engineer, Sept 15, 2026):
  - Pipeline: outcome → context gathering → implement → CI → multiple specialist review agents → agentic deploy → monitoring → "Perf Factory" → Sevbot for incidents.
  - Saw roughly a 10x increase in PR load.
- **Gas Town / Gas City** (Steve Yegge): a "Mayor" agent dispatching 20–30 parallel agents, with Beads as an issue tracker that doubles as agent memory.
- **[awesome-software-factories](https://github.com/vitalik1921/awesome-software-factories)**: a catalog of factories, Ralph loops, session managers, sandboxes, spec tools and review gates.

---

## 7. Learning resources

### Paid

| Resource | Format | Price | Notes |
|---|---|---|---|
| Matt Pocock: AI Coding for Real Engineers | 2-week cohort, Nov 9 | ~$795 USD (past) | Build your own factory; Sandcastle + skills |
| IndyDevDan: [Tactical Agentic Coding](https://agenticengineer.com/tactical-agentic-coding) | Self-paced, 6.5h + repos | $599 | "Out of the loop," AI Developer Workflows, "Zero-Touch Engineering." **(quality unverified)** |
| Actual AI: [Software Factory Intensive](https://actual.ai/softwarefactory) | 2-day in person (Seattle Oct 14–15) | Not listed | Vendor-led, built around their own agents |

### Free, in suggested reading order

1. [Dan Shapiro: The Five Levels](https://danshapiro.spicytakes.org/post/2026-01-23-the-five-levels-from-spicy-autocomplete-to-the-software-factory)
2. [Paul Iusztin: Inside a Software Factory](https://www.oreilly.com/radar/inside-a-software-factory/)
3. [Dex Horthy: Why Software Factories Fail](https://www.youtube.com/watch?v=Ib5GBkD555M)
4. [Matt Pocock: Fixing the PR Bottleneck](https://finance.biggo.com/news/4884c941b185405c) and the [software factory definition](https://www.aihero.dev/ai-coding-dictionary/software-factory)
5. Sandcastle README and templates
6. [Mastra tutorial](https://mastra.ai/blog/software-factory) and the [Symphony spec](https://www.infoq.com/news/2026/05/openai-symphony-agents/)
7. [Peter Roelants: Dark Software Factories](https://gist.github.com/peterroelants/0e22b06ff5069c317dfda2192a83d28f)
8. [Every: Compound Engineering](https://every.to/guides/compound-engineering)
9. [Nate Jones on StrongDM](https://natesnewsletter.substack.com/p/the-20kmonth-lobster-that-zuckerberg)

---

## 8. Starter plan for the repo (draft)

A light factory, grown one bottleneck at a time.

### Phase 0: Foundations

- Pick one TypeScript target repo (not FileMaker).
- Write `CONTEXT.md` / `CLAUDE.md`: domain model, conventions, architecture boundaries.
- Make automated checks solid: lint, typecheck, tests, all runnable with one command.
- Define the issue format and labels: `needs-spec` → `ready-for-agent` → `agent-in-progress` → `needs-human-review` → done.

### Phase 1: One AFK loop

- Sandcastle `sequential-reviewer` (or a Claude Code Routine) triggered by the `ready-for-agent` label.
- Reviewer agent in its own context window; it commits fixes.
- Human reviews the PR. Log tokens and time for each run.

### Phase 2: The learning loop

- After every human review, run a retro: is this a new lint rule, test, reviewer instruction or skill update?
- Track the rate of human corrections over time. It should trend down.

### Phase 3: Parallelism

- `parallel-planner-with-review`; cap the number of concurrent agents.
- Add triggers: CI failure → fix agent; nightly → dependency and housekeeping agent.

### Phase 4: Decide on human review case by case

- Classify changes as reversible or one-way-door. Auto-merge only reversible changes that pass every gate.
- Compare against Anthropic Projects threads and Routines once local execution lands.

### Open questions

- How Claude Code authenticates in containers (subscription vs API key)
- Where it runs: the Mac mini, the cloud, or both. Some work needs TC network access.
- Factory visibility: whether the session time tracker logs agent runs
- Whether to wait for the Matt cohort (Nov 9) before locking in the architecture
