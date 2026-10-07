# CLAUDE.md — dc-dev-plugins marketplace

This repo is a **Claude Code plugin marketplace** (`datacraftdevelopment/dc-dev-plugins`). One `.claude-plugin/marketplace.json` lists every plugin; each plugin is a self-contained subfolder with its own `.claude-plugin/plugin.json`. Installed once per machine (`/plugin marketplace add datacraftdevelopment/dc-dev-plugins`), then plugins are installed individually.

Current plugins: **`pm`** (project-management scaffold + session/delivery skills, the hands-on way of working), **`factory`** (Runway, the unattended ticket loop, and its `runway` skill; source `factory/plugin/`), **`design-dc`** (design workflow), **`fm-dc`** (agentic FileMaker development), **`ui-test`** (agent-run UI tests for any macOS app: Codex computer-use runner + verifier under Ringer, per-app target profiles), **`fm-lens`** and **`agenticdev-filemaker-standards`** (listed here, sourced from the private `FM_Agent_Lens` repo), **`basecamp-dc`** (Basecamp client-face conventions + quirk-safe shipping; opt-in per repo via `.basecamp/config.json`, inert without it, never a `pm` dependency — TC uses Jira, most projects use no client tracker), and **`sdlc`** (the machine-wide credential-guard hook, moved from pm on 2026-10-07, plus repo-level enforcement kits: gate hooks installed into a repo's `.claude/` and a `REVIEW.md` policy with a read-only reviewer; it depends on neither `pm` nor Ringer, and its Codex edition carries only the credential guard, per `CODEX_PARTS` in `scripts/build_codex.py`).

**This repo is PRIVATE** (2026-09-03; renamed from `dc-plugins` 2026-09-12 — that name now belongs to the PUBLIC marketplace cut by `make-dc-plugins.sh`). `/plugin marketplace add` still works unchanged, but each machine needs an authenticated `gh`/git credential helper for `datacraftdevelopment`. It went private so pm can hard-wire tools that aren't public — `WORKFLOW.md` assumes Ringer, which lives in the private `datacraftdevelopment/desk` — and so nothing here is written for strangers. The teaching channel is `FMTrainingTV-AI/rcc-fm` (public, separate org); the `fm-dc → fm-rcc` sync runs locally (`make-fm-rcc.sh`) and DataCraft's public `datacraftdevelopment/dc-plugins` is cut from that (`make-dc-plugins.sh`); `tc-plugins` (the TC Transcontinental edition, Joe's personal credit, separate GitHub account) is cut from the public tree (`make-tc-plugins.sh`), a plain copy. The shared editions (RCC and TC) carry the same pm and sdlc from 2026-10-04: the private `sdlc/` plus `portable-overlay/` (adversary reviewer subagent, `ship-acceptance`, a shared `WORKFLOW.md`), hand-passed into `rcc-plugins`; its README has the steps. They run on Claude Code only, so nothing there may name Ringer. Derived trees are never hand-edited — fix upstream, re-cut down the chain.

## Ringer is assumed

Every delegated model call in these plugins goes through **Ringer** (`~/Agentic-Mini/_Core/Ringer`, `ringer` on PATH); the `ringer` / `cross-review-gate` / `build-swarm` skills live in `_Core/library/skills/agent-operations/`, not here. `pm`'s `fast-grill`, the build loop, and the review gate all dispatch through it — never inline Codex. If a skill you are writing needs a second model, route it through Ringer and say so in the skill; the README's "What this repo assumes" section is the one place that dependency is documented, so update it there rather than restating it per skill.

## ⚠️ Pre-flight: adding or copying a plugin/skill INTO this repo

These plugins are **shared across machines via git**. A file that works locally can silently break on another machine. Before adding a plugin or skill — and before claiming it works — run every check below. Each one is a gotcha we have actually hit.

1. **Symlinks — the #1 gotcha.** `cp -R` copies a symlink as a link, not its target, so anything symlinked out (e.g. a skill kept in iCloud/Obsidian and linked into `~/.claude/skills/`) ships as a dangling reference that won't resolve on install.
   ```bash
   git -C <source> ls-files -s | awk '$1=="120000"'      # any output = a committed symlink
   find <source-dir> -type l                              # untracked symlinks
   ```
   Fix: dereference into real files — `cp -RL`, or `rm link && cp -R <resolved-target> <dest>`.

2. **Copy git-tracked files ONLY.** A raw `cp -R` drags in `.venv/`, `sandbox/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, and possibly **client data**. Copy the committed set instead:
   ```bash
   git -C <source> archive HEAD | tar -x -C <dest>
   ```
   Then confirm none of those dirs landed in `<dest>`.

3. **No machine-specific absolute paths** in shipped files:
   ```bash
   git -C <source> grep -n "/Users/" -- '*.md' '*.py' '*.json' '*.txt'
   ```
   Rewrite install/usage docs to the marketplace form (`/plugin install <name>`), not `claude --plugin-dir /Users/...`. (Provenance notes in `VENDOR.md` are fine.)

4. **Tool invocation must be portable.** Scripts must be called via `python3 ${CLAUDE_PLUGIN_ROOT}/…` (or the equivalent root var), never a hardcoded `.venv/bin/python` — the venv does not travel. Runtime deps go into **system `python3`** per machine; document them (fm-dc: `pip3 install lxml requests python-dotenv`).

5. **No name collisions** across plugins — commands, skills, and agents share their namespaces:
   ```bash
   ls */commands */skills */agents 2>/dev/null   # eyeball for dupes across plugins
   ```

6. **Validate every manifest is real JSON:**
   ```bash
   python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('**/.claude-plugin/*.json', recursive=True)]; print('OK')"
   ```

7. **Test from the NEW location, not the source.** If the plugin has a suite, run it here after the move — parity is the only proof the copy is complete (fm-dc: `cd fm-dc && .venv/bin/python -m pytest tests -q`).

8. **Bump the plugin's `version`** in its `plugin.json` on any shipped change, so `/plugin marketplace update` actually pulls it.

## Renaming a plugin — watch for name-shaped strings that aren't the name

A plugin's name drives its command namespace (`/<plugin>:<command>`), but the same token often appears as **config filenames or cache paths hardcoded in code** (e.g. fm-dc reads `fm-dc.json` and writes `~/.fm-dc/`). Those are NOT the plugin name — a blind find-replace breaks the tools. Change the namespace refs; leave the hardcoded data paths.

## Dev workflow

Develop **in place** in each plugin's subfolder — this repo is the single source of truth (standalone plugin repos were retired). Ship a change: commit + push, then `/plugin marketplace update dc-dev-plugins` on each machine. Add a new plugin: new subfolder + one line in `marketplace.json` — never a new marketplace.

`pm/template/` is designed **in place** here too — the DC-Project-Builder mirror was retired 2026-08-28 (`docs/intent/pm-010-lightening.md`); the builder repo (`datacraftdevelopment/dc-project-builder`) is dormant and no longer receives scaffold changes. Its `docs/_design/` history names client paths and must never ship here (scrubbed once already, pm v0.2.2) — that rule outlives the mirror.

Per-plugin dev cruft (`.venv/`, `sandbox/`) is gitignored via each plugin's own nested `.gitignore`, so it never publishes.

## `factory/` — research, plus the factory plugin in `factory/plugin/`

`factory/` is the software-factory research and the Runway experiments (was `_Tools/SoftwareFactory`, folded in 2026-10-07 by subtree merge, history kept), plus the factory site in `factory/site/`. Only `factory/plugin/` ships: `marketplace.json` lists it as `factory`, and `scripts/build_codex.py` maps the name to that folder (`SOURCES`). The research, experiments and site never ship, and the `make-*.sh` cuts copy none of it. The experiments' tests run against the engine in `factory/plugin/runway/`; the old `factory/experiments/01-runway/runway.py` and `03-linear/schedule.sh` are forwarding stubs for LaunchAgents installed before the move. `factory/CLAUDE.md` governs work inside it. Practice repos stay outside git in `~/Agentic-Mini/_Sandbox/runway/`.

## Tracking (`_pm/`, local-only)

Root `_pm/` holds personal dev tracking (skeleton, TASKS, sessions) via the `pm` plugin's `whats-next` / `stepping-away` skills. It is **gitignored** (`/_pm/`, anchored so it doesn't touch `pm/template/_pm/`) — never published. This repo moved out of Dropbox to `~/Agentic-Mini` on 2026-09-12 (Dropbox was causing too many issues); `_pm/` no longer syncs between machines on its own, so it rides on whatever backup covers `~/Agentic-Mini`.
