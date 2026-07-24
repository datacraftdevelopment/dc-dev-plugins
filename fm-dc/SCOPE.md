# fm-dc — DataCraft Agentic FileMaker Plugin — Scope

**Author:** Joe DaSilva / DataCraft Development (drafted with Claude)
**Date:** 2026-07-06
**Status:** Approved 2026-07-06 — Phases 0–2 built (see README); Phases 3–4 pending
**Catalyst:** Industry movement toward agentic FileMaker development (2026-07-06). Verdict: the direction validates bets DataCraft already made — and DataCraft holds assets not yet shipped.

---

## 1. Purpose

Build **one Claude Code plugin — `fm-dc`** — that turns any Claude Code session into a competent FileMaker developer using DataCraft's own tooling and conventions. The plugin consolidates capability that today is scattered across two repos:

- `~/Dropbox/_Bots/_starters/datacraft-Project-FM` — 13 project-local skills, the DDR/Save-as-XML analysis engine, fmlint snippet validation, the per-client plugin model, connection doctrine, ProofKit playbooks
- `~/Dropbox/DC_Code/_RCC/FM-Patch-Agent` — the patch pipeline: headless export, SaXML parse/diff, auto-generated FMUpgradeTool patches with dependency resolution, safe apply with verify, spec-driven file scaffolding, 131 tests

Today that capability only exists *inside those project folders*. The plugin makes it installable: every FM engagement gets it for free, projects stay thin, and per-client knowledge lives in a small overlay kit instead of a forked toolchain.

**Core capabilities (from the brief):**

1. Knowing how to use **ProofKit** (MCP, web viewer apps, fmdapi/typegen/fmodata)
2. Knowing how to **connect to FileMaker servers** (Data API, OData, Admin API, ProofKit MCP — the four-mode doctrine)
3. Knowing the **XML** (SaXML grammar, fmxmlsnippet clipboard formats, DDR)
4. Knowing how to **patch FileMaker files** (export → diff → patch → verify, with rollback)
5. **`/fm-scaffold`** — scaffold a project folder the DataCraft way, minimized
6. **Baked-in FileMaker documentation** — local-first, no runtime internet dependency

## 2. Context: what Claris showed, and what it changes

Their architecture is **skills + agents + tools**:

- **Skills** — pre-synthesized references for every FM function/calculation; no internet lookups at runtime
- **Agents** — specialty roles: script builder, schema builder, patch builder, orchestrator, XML validator
- **Tools** — deterministic XML compilation. The model never invents XML shape; it interprets intent and slots values into known shapes. Result: syntax is always right (even on mid-tier models), only logic can be wrong.

Their delivery mechanism is the **patch tool** (FMUpgradeTool) with **clipboard fallback** where patching falls short. `/filemaker-init` scaffolds claude.md + a Save-as-XML baseline + a folder structure holding **before/after states per patch** for full rollback, plus a default **change log**. After a patch, only the touched catalog is re-exported to verify the patch landed. Customization survives updates via a **core plugin + overlay plugin** split. Quality is enforced by a trusted prompt battery (~84 score; 604 tests for script steps alone) and a session-timing command for telemetry.

**Their admitted gaps:** modifying scripts in place (inserting steps), the layout object catalog, custom-function edge cases, anything with no clipboard equivalent (accounts, privilege sets), **single-user local-file constraint**, and **no hosted-file story** — they said themselves the long-term answer is a direct API that doesn't exist yet.

**What this changes for DataCraft:** nothing about direction — FM-Patch-Agent's June decision record ("pure CLI: FMDeveloperTool export, FMUpgradeTool patch, verify by re-export; revisit when Claris previews land") anticipated exactly this. What it adds is (a) architectural confirmation, (b) a checklist of ideas worth adopting (deterministic compilation, sub-agent roles, scoped verification, overlay split), and (c) a clear view of the gaps where DataCraft is already ahead.

## 3. Assets going in

| Asset | Lives today | State | Lands in plugin as |
|---|---|---|---|
| `gen_patch.py` — diff→FMUpgradeTool patch generator (identity remapping, dependency graph, catalog ordering) | FM-Patch-Agent/scripts | Mature, tested | **Tool** (crown jewel — Claris's own docs call this workflow manual) |
| `apply_patch.py` — backup → validatePatch → smoke → in-place → verify-by-re-export, auto-restore | FM-Patch-Agent/scripts | Mature, battle-tested | **Tool**, driven by patch-builder agent |
| `fm_export.py` — headless FMDeveloperTool SaXML export, AppleScript close/reopen, lsof lock check | FM-Patch-Agent/scripts | Mature | **Tool** |
| `saxml_parser.py` / `saxml_diff.py` — per-catalog JSON snapshots, patchability tiers (proven/caution/manual) | FM-Patch-Agent/scripts | Mature | **Tool** |
| `make_review.py` — interactive HTML review artifact → selection.json | FM-Patch-Agent/scripts | Mature | **Tool** (human approval gate) |
| `gen_scaffold.py` — JSON spec → .fmp12 via seed file, reconciler semantics | FM-Patch-Agent/scripts | Prototype-plus (one real E2E) | **Tool**, later fronted by schema-builder agent |
| `workflows/` — export-xml, diff-review, patch-apply, scaffold-file SOPs | FM-Patch-Agent | Distilled from 10+ real runs | **Agent system prompts + fm-patch skill** |
| `patchability-matrix.md` — object×operation grid, ground truth from real tool runs | FM-Patch-Agent/docs | Mature | **fm-patch skill reference** |
| 131-test suite incl. OOE conformance + sandbox E2E | FM-Patch-Agent/scripts/tests | Passing | **Plugin test suite** |
| `ddr.py` engine — split/summary/search/refs/orphans/compare/readable; auto-detects classic DDR + FM 2026 split-catalog | starter/scripts | Mature | **Tool** |
| fmlint (`validate_snippet.py`) — snippet linting, vendored agentic-fm | starter/scripts | Mature | **Tool** |
| Kear skills ×3 — script/CF, layout, field clipboard XML specs | starter/.claude/skills | Vendored, current | **fm-xml skill references** |
| `filemaker` skill — calcs, script patterns, FM 2024–2026 features | starter/.claude/skills | Mature | **fm-core skill** |
| `fm` skill + `fm_client.py` — Data API/OData CLI, zero-dep client | starter | Mature | **fm-connections skill + tool** |
| Four-mode access doctrine (ProofKit MCP / Data API / OData / schema pipeline) | starter/CLAUDE.md | Proven | **fm-connections skill core** |
| ProofKit playbooks — webviewer build guide, fmdapi/typegen/fmodata stack, MCP tool guide | starter/docs | Proven, with real gotchas | **fm-proofkit skill** |
| Claris markdown docs map — llms.txt corpus, URL patterns, mirror recipe | starter/docs/reference | Verified 2026-06 | **fm-docs skill + `/fm-docs-sync`** |
| `ooe-source.md` (One-of-Everything file), `ddr_xml_structure.md` | starter/docs/reference | Current | **fm-xml skill references + test fixtures** |
| Per-client kit model — primer/connection/schema/glossary/recipes/guardrails | starter/plugin | Proven with real clients | **Overlay template + `/fm-client-kit`** |
| ProofKit MCP + FileMaker OData MCP servers | Already configured in Joe's environment | Working | Referenced by skills (not bundled) |

## 4. Position vs. the Claris toolkit

| Capability | Claris beta | DataCraft today | Verdict |
|---|---|---|---|
| Patch mechanism | FMUpgradeTool + clipboard fallback | Same tools | **Parity** (same foundation) |
| Diff → patch generation | Not shown; intent→patch only | Automated w/ dependency graph, tiers, review UI | **Ahead** |
| Safe apply + rollback | Before/after folders, backup | backup→validate→smoke→verify→auto-restore | **Parity+** (ours verifies against re-export, theirs keeps per-patch states — adopt that) |
| Intent → change (build me a script) | Deterministic XML compile → patch | Model-written snippet XML (Kear specs) → fmlint → clipboard paste | **Behind** (their #1 idea worth adopting) |
| Script-step coverage guarantees | 604 deterministic tests | fmlint catalog + OOE conformance tests | **Behind** (scale gap; close progressively) |
| Live verification against the running DB | None (XML-only; testability acknowledged as unsolved) | ProofKit MCP (DDL, SQL, layout metadata) + Data API + OData | **Ahead** |
| Hosted files | Explicitly unsolved | Mapped: server-side Save-as-XML script step (19.5+), Admin API close/download/open, OData live schema mutations | **Ahead** (their #1 gap) |
| Server connectivity as a first-class skill | Not in scope | Four-mode doctrine, proven | **Ahead** |
| Web viewer / modern UI | "Coming soon" | ProofKit playbook with production gotchas | **Ahead** |
| Per-solution customization | Core+overlay split (write-up pending) | Per-client kit proven with real clients | **Ahead** (same idea, ours is shipped) |
| Sub-agent role structure | 5 named agents | Workflows-as-markdown, main-loop orchestration | **Behind** (adopt: it's cheap to do) |
| Session telemetry | Timing command + bundle | None | **Behind** (low priority) |
| Init UX | Polished one-shot `/filemaker-init` | Manual per-project setup | **Behind** (build `/fm-init`) |

**Positioning:** fm-dc is not a Claris-toolkit clone. It's the DataCraft harness: same deterministic foundations, plus the three things they don't have — a **live hosted loop** (tables/fields over OData + generated XML pasted into the open file, so the file never comes down), live-database verification, and a proven client-kit overlay. The patch tool is a *local-and-closed* mechanism — the only door that moves **whole layouts, relationships, and table occurrences**, plus dev→prod migration and build-from-a-starter — a first-class door, but the same offline constraint Claris has, not the daily loop. (Accounts, privilege sets, custom menus and security stay a human's job in every lane.) When Claris ships publicly, their patch improvements become a swappable backend under our agents, not a replacement for the harness.

## 5. The plugin

```
fm-dc/                                  ← this repo, installable Claude Code plugin
├── .claude-plugin/plugin.json          ← name, version, (optional) mcpServers refs
├── CLAUDE.md                           ← plugin dev guide (for working ON fm-dc)
│
├── commands/
│   ├── fm-init.md                      ← adopt a .fmp12/project: doctor checks, config, SaXML baseline, change log
│   ├── fm-scaffold.md                  ← DataCraft project folder, minimized by default
│   ├── fm-status.md                    ← file/config/baseline/patch-history at a glance
│   ├── fm-rollback.md                  ← restore from timestamped backup / before-state
│   └── (later) fm-timing.md, fm-client-kit.md, fm-docs-sync.md
│
├── agents/
│   ├── fm-patch-builder.md             ← owns the patch transaction end-to-end
│   ├── fm-xml-validator.md             ← adversarial checker: lint, re-export diff, live checks
│   └── (later) fm-schema-builder.md    ← spec-driven scaffold/reconcile
│
├── skills/
│   ├── fm-core/                        ← calcs, scripting patterns, FM 2024–2026 features
│   ├── fm-xml/                         ← SaXML grammar, snippet formats (Kear ×3 merged as references/), OOE
│   ├── fm-patch/                       ← pipeline doctrine, patchability matrix, when-patch-vs-clipboard
│   ├── fm-connections/                 ← four-mode doctrine, fm_client.py, OData, Admin API, .env conventions
│   ├── fm-proofkit/                    ← MCP usage, webviewer playbook, fmdapi/typegen/fmodata stack
│   └── fm-docs/                        ← baked reference: synthesized catalogs + local Claris-docs mirror
│
├── tools/                              ← deterministic, Python, model never rewrites these
│   ├── patch/                          ← fm_export, saxml_parser, saxml_diff, gen_patch, apply_patch,
│   │                                      make_review, gen_scaffold, saxml_ignore.json
│   ├── ddr/                            ← ddr.py, fmsaveasxml.py, readable.py, ddr_xml_utils.py
│   ├── fmlint/                         ← vendored linter
│   └── genobj/                         ← NEW: shape-catalog compiler (intent → known XML shapes)
│
├── templates/
│   └── scaffold/                       ← what /fm-scaffold copies (minimized starter skeleton)
└── tests/                              ← ported 131 + golden shapes + prompt battery
```

### 5.1 Skills (six)

| Skill | Sourced from | Triggers on |
|---|---|---|
| `fm-core` | starter `filemaker` | any FM development question |
| `fm-xml` | Kear ×3 + `ooe-source` + `ddr_xml_structure` | writing/reading any FM XML |
| `fm-patch` | FM-Patch-Agent workflows + patchability matrix | "apply/patch/deploy this change to the file" |
| `fm-connections` | starter `fm` skill + four-mode doctrine + integration guide | "connect / query / mutate schema on a server" |
| `fm-proofkit` | proofkit.md + webviewer playbook | web viewer apps, typegen, MCP bridge work |
| `fm-docs` | Claris llms.txt map + synthesized catalogs | "what does script step X do", exact option names |

Consolidation rule: skills merge by *when they trigger*, not by source file. The three Kear skills become `references/` inside `fm-xml` (progressive disclosure keeps token cost identical), so one skill owns "producing XML."

### 5.2 Sub-agents (the workflows → agents conversion)

The instinct in the brief is right, with one boundary: **workflows that are long, tool-heavy, and transactional become sub-agents; the orchestrator does not.** Claude Code's main loop *is* the orchestrator — a separate orchestrator agent would just add a telephone game.

- **`fm-patch-builder`** — wraps the patch-apply workflow. Input: an approved change set (diff selection or generated objects). It runs export → gen_patch → apply_patch → verify, returns a compact report (patch path, backup path, verify result, change-log entry). Rationale: a patch transaction burns thousands of tool-output tokens the main conversation never needs; isolation also enforces the safety choreography — the agent's prompt *is* the SOP, so "never bypass validate→smoke→verify" stops being a convention and becomes the only path.
- **`fm-xml-validator`** — adversarial verifier with fresh context: fmlint on snippets, scoped re-export + re-diff after patches (Claris-style: only touched catalogs), optional live checks via ProofKit MCP / Data API when a server is reachable. Kept separate from the builder so the checker isn't grading its own homework.
- **`fm-schema-builder`** (Phase 4) — fronts `gen_scaffold.py` for spec-driven builds/reconciles. Stays a workflow until the reconciler has more real-file mileage.
- **export-xml and diff-review stay in the main loop** — they're short, interactive (the human ticks checkboxes in the review artifact), and benefit from conversation context.

### 5.3 Commands

- **`/fm-init`** — adopt an existing file/project (the Claris `/filemaker-init` equivalent): doctor checks (FMDeveloperTool, FMUpgradeTool, Python deps, .env), write `fm-dc.json` (array of managed files + credentials refs), take the baseline SaXML export, create `patches/` (before/after per patch), start `changelog.md`.
- **`/fm-scaffold`** — the DataCraft project folder, **minimized by default**: `_pm/` (skeleton, TASKS, sessions), `schema/`, `dev/`, `.env.example`, project CLAUDE.md stub. Flags: `--full` (webviewer/, web/, docs/ tree — the whole starter shape), `--client-kit` (adds the per-client overlay skeleton). The starter repo stops carrying FM skills; the plugin carries capability, the scaffold carries structure.
- **`/fm-status`**, **`/fm-rollback`** — thin wrappers over the patch engine's artifacts (config, baselines, backups, change log).
- **Later:** `/fm-timing` (session telemetry à la Claris), `/fm-client-kit` (generate a client overlay from a parsed DDR + glossary interview), `/fm-docs-sync` (build/refresh the local docs mirror).

### 5.4 Baked-in documentation (requirement #6)

Two layers, because licensing and determinism are different problems:

1. **Synthesized catalogs (ship with the plugin).** Original DataCraft-authored reference distilled from the OOE file, real SaXML exports, and round-trip tests: script-step XML shapes with slot definitions, function signatures, element-ordering rules, silent-failure gotchas. This is what `genobj` compiles from, it's redistributable, and it's the plugin's ground truth.
2. **Claris docs mirror (fetched once, then local).** `/fm-docs-sync` pulls curated sets from the llms.txt markdown corpus (~1,100 pro-help pages + Data API/OData/App Upgrade Tool guides) into a local cache using the recipe already in `claris-markdown-docs-reference.md`. Runtime lookups hit the cache first, URL only as fallback. We don't redistribute Claris's corpus inside the plugin — each install mirrors its own.

### 5.5 The overlay model (per-client kits)

Unchanged from the proven starter model, now formalized as the plugin's second tier: **fm-dc core is generic; each client gets a small overlay plugin** (schema.md, glossary.md, recipes.md, connection.md, guardrails.md, samples/) generated by `/fm-client-kit`. Core updates never touch overlays — the exact property Claris promised for their overlay, already shipped here. The existing client-kit `fm_client.py` + primer stay the client-side runtime.

## 6. Design decisions

1. **One core plugin + thin overlays** — capability in `fm-dc`, per-client/solution knowledge in overlay kits, project folders scaffolded thin. (Mirrors Claris core/overlay; continues the DataCraft client-kit model.)
2. **Deterministic XML, adopted progressively.** Endorse Claris's principle: the model interprets intent; tools compile XML. `gen_patch`/`gen_scaffold` already work this way. New `genobj` tool extends it to object creation — starting with the **top ~30 script steps** (covers the bulk of real scripts), model+Kear+fmlint remains the fallback for the tail. We do not attempt 604-test coverage in v1; we grow the catalog by usage, each shape landing with a golden round-trip test.
3. **Sub-agents for transactions, main loop for orchestration** (§5.2).
4. **Patch tool primary, clipboard fallback, tier-gated** — the patchability matrix decides the route mechanically: proven → patch; caution → patch with `--allow-caution` + human ack; manual → clipboard via fm-xml (script-step inserts, layout objects) or hard stop (accounts/privilege sets). Same fallback logic Claris described, but ours is encoded as data, not vibes.
5. **Docs: synthesize what we compile from; mirror what we look up** (§5.4).
6. **Adopt Claris's per-patch before/after states** alongside our timestamped backups + rolling change log — cheap, and it makes `/fm-rollback` trivially explainable.
7. **The starter slims down.** datacraft-Project-FM keeps the PM layer and engagement structure; its 8 FM skills and scripts move into the plugin (single source of truth; no more per-project drift). The starter declares fm-dc as a prerequisite.
8. **Hosted-file lane is the flagship differentiator** (Phase 4): fmdapi `executeScript` → server-side Save-a-Copy-as-XML → Admin API close/download → local patch → re-upload/open; OData for live table/field adds without closing at all. This is the gap Claris told the whole beta they haven't solved.
9. **MCP servers referenced, not bundled.** proofkit-mcp and the FileMaker OData MCP stay user-level; skills detect and use them when present, degrade to CLI paths when not.

## 7. Out of scope (v1)

- Layout object *generation* beyond clipboard snippets (Claris calls it their hardest catalog; ours too)
- Accounts / privilege sets automation (no patch or clipboard path exists — document as manual)
- Multi-user concurrent patching (single-user local constraint is inherent to the tool; change log is the audit proxy)
- Windows support (pipeline is macOS: AppleScript, /usr/local/bin tools)
- Claris-style 604-test determinism (progressive catalog instead)
- Modern UI generation beyond the existing ProofKit webviewer path
- Public marketplace distribution (private/team install first; revisit after client use)

## 8. Testing & quality

- **Port the 131-test suite** as-is (skips gracefully without Claris CLI tools).
- **Golden shape tests**: every `genobj` shape ships with scaffold → patch → re-export → byte-compare-normalized round-trip (the sandbox E2E harness already does this dance).
- **OOE conformance** stays the canonical fixture.
- **Prompt battery** (~25 prompts to start): the Claris "trusted suite" idea at DataCraft scale — build script / add table+fields / modify calc / rollback / hosted read — scored pass/fail per release.
- **fmlint gate** on every snippet the model authors, no exceptions.

## 9. Roadmap

| Phase | Delivers | Done when | Rough effort |
|---|---|---|---|
| **0 — Bootstrap** | Repo + manifest; vendor patch engine, ddr engine, fmlint into `tools/`; tests green | `claude --plugin-dir` install works; 131 tests pass from new home | 1–2 sessions |
| **1 — Skills + scaffold** | 6 skills consolidated; `/fm-scaffold`; `/fm-init` with doctor | New empty folder → init → scaffold → agent answers FM/ProofKit/connection questions from plugin skills alone | 3–5 sessions |
| **2 — Patch agents** | `fm-patch-builder`, `fm-xml-validator`; before/after states; `/fm-status`, `/fm-rollback`; change log | Real change lands on sandbox file via sub-agent, verified + rolled back cleanly | 3–4 sessions |
| **3 — Deterministic gen + docs** | `genobj` top-30 script steps + golden tests; synthesized catalogs; `/fm-docs-sync`; prompt battery | "Create a script that finds/sorts/exports" compiles deterministically, patches in, verifies — offline | 5–8 sessions |
| **4 — Differentiators** | Hosted-file lane; `/fm-client-kit`; `fm-schema-builder` agent; `/fm-timing` | Hosted file patched end-to-end without manual download; client kit generated from a DDR | 6–10 sessions |

Phases 0–2 ≈ two part-time weeks and already exceed the beta toolkit *for DataCraft's workflow*. Phase 3 closes the determinism gap where it matters; Phase 4 is the moat.

## 10. Risks & mitigations

- **Claris ships publicly and improves fast.** Mitigation: fm-dc's value is the harness + hosted lane + client kits, not the patch mechanism; their tool can become a backend under `fm-patch-builder`. Beta participation keeps the roadmap informed.
- **Beta confidentiality.** fm-dc vendors nothing from the beta plugin. Everything here is DataCraft code predating the beta (FM-Patch-Agent: June 2026) plus public Claris docs. The transcript informs positioning only. Keep it that way — don't lift their skill files even for "inspiration."
- **FMUpgradeTool quirks** (the "Patch File Applied" banner lies; replace-action issues; version matching). Mitigation: already encoded — verify-by-re-export is mandatory, patch version pinned to export version, tiers gate generation.
- **Doc-mirror staleness / licensing.** Mirror is user-fetched, dated, refreshed by `/fm-docs-sync`; synthesized catalogs are original work.
- **Scope creep toward Claris feature-chasing.** The prompt battery + this scope doc are the fence: build what DataCraft engagements need, adopt their ideas only when a phase calls for it.
- **Single-maintainer bus factor.** Tests + SOP-as-agent-prompt keep the choreography executable by any session, not just by memory.

## 11. Open questions (for review)

1. **Name/branding:** `fm-dc` (matches this folder) vs `datacraft-fm` — affects command namespace (`/fm-dc:fm-init` vs `/datacraft-fm:fm-init`).
2. **FM-Patch-Agent repo fate:** absorb into `tools/patch/` and archive the repo, or keep it as the upstream lab and vendor snapshots? (Recommend: absorb; the _demo/presentation history stays archived in place.)
3. **`/fm-scaffold` default:** is the "minimized" set right — `_pm/` (lite), `schema/`, `dev/`, `.env.example`, CLAUDE.md stub — or should `docs/` (quirks/learnings) be in the default too?
4. **genobj step catalog:** which 30 script steps first? (Proposal: pull frequency ranks from existing client DDRs via `ddr.py` rather than guessing.)
5. **Overlay packaging:** client kits as separate installable plugins (current model) or as a `.claude/skills/` drop-in per project? Plugin keeps versioning; drop-in is simpler for small clients.
6. **Beta feedback loop:** how much of the developer-journey report doubles as fm-dc requirements gathering? (3 hrs/week commitment; Fridays 10 a.m. PT office hours.)

---

*Sources: Granola transcript "Claris Agentic" (2026-07-06); `datacraft-Project-FM/CLAUDE.md`, `docs/filemaker-ai-kit-vision.md`, `docs/reference/fm-cli-tooling-landscape.md`, `docs/reference/claris-markdown-docs-reference.md`; FM-Patch-Agent `README.md`, `CLAUDE.md`, `workflows/`, `scripts/`, `docs/patchability-matrix.md`.*
