# CLAUDE.md — dc-plugins marketplace

This repo is a **Claude Code plugin marketplace** (`datacraftdevelopment/dc-plugins`). One `.claude-plugin/marketplace.json` lists every plugin; each plugin is a self-contained subfolder with its own `.claude-plugin/plugin.json`. Installed once per machine (`/plugin marketplace add datacraftdevelopment/dc-plugins`), then plugins are installed individually.

Current plugins: **`pm`** (project-management scaffold + session/delivery skills), **`design-dc`** (design workflow), **`fm-dc`** (agentic FileMaker development), and **`ui-test`** (agent-run FileMaker UI tests: Codex computer-use runner + verifier under Ringer).

**This repo is PRIVATE** (2026-09-03). `/plugin marketplace add` still works unchanged, but each machine needs an authenticated `gh`/git credential helper for `datacraftdevelopment`. It went private so pm can hard-wire tools that aren't public — `WORKFLOW.md` assumes Ringer, which lives in the private `datacraftdevelopment/desk` — and so nothing here is written for strangers. The teaching channel is `FMTrainingTV-AI/rcc-fm` (public, separate org); the `fm-dc → fm-rcc` sync runs locally and is unaffected.

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

Develop **in place** in each plugin's subfolder — this repo is the single source of truth (standalone plugin repos were retired). Ship a change: commit + push, then `/plugin marketplace update dc-plugins` on each machine. Add a new plugin: new subfolder + one line in `marketplace.json` — never a new marketplace.

`pm/template/` is designed **in place** here too — the DC-Project-Builder mirror was retired 2026-08-28 (`docs/intent/pm-010-lightening.md`); the builder repo (`datacraftdevelopment/dc-project-builder`) is dormant and no longer receives scaffold changes. Its `docs/_design/` history names client paths and must never ship here (scrubbed once already, pm v0.2.2) — that rule outlives the mirror.

Per-plugin dev cruft (`.venv/`, `sandbox/`) is gitignored via each plugin's own nested `.gitignore`, so it never publishes.

## Tracking (`_pm/`, local-only)

Root `_pm/` holds personal dev tracking (skeleton, TASKS, sessions) via the `pm` plugin's `whats-next` / `stepping-away` skills. It is **gitignored** (`/_pm/`, anchored so it doesn't touch `pm/template/_pm/`) — never published. This repo moved out of Dropbox to `~/Agentic-Mini` on 2026-09-12 (Dropbox was causing too many issues); `_pm/` no longer syncs between machines on its own, so it rides on whatever backup covers `~/Agentic-Mini`.
