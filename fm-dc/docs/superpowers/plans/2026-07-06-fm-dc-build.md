# fm-dc Plugin Build — Implementation Plan (Phases 0–2 + stubs)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the installable `fm-dc` Claude Code plugin per [SCOPE.md](../../../SCOPE.md): vendored deterministic tools, consolidated skills, patch sub-agents, and init/scaffold commands.

**Architecture:** Vendor mature code from FM-Patch-Agent (`~/Dropbox/DC_Code/_RCC/FM-Patch-Agent`) and datacraft-Project-FM (`~/Dropbox/_Bots/_starters/datacraft-Project-FM`) into `tools/`; consolidate their skills into plugin `skills/`; author commands + agents as markdown that drive the tools via `${CLAUDE_PLUGIN_ROOT}`. Phase 3–4 items ship as stubs (`tools/genobj/`, `/fm-docs-sync` is real but cheap).

**Tech Stack:** Claude Code plugin layout (`.claude-plugin/plugin.json`, `commands/`, `agents/`, `skills/`), Python 3.14 + lxml + pytest (project venv), Claris CLI tools (present at `/usr/local/bin`).

## Global Constraints

- Patch scripts use flat sibling imports (`import fm_export, saxml_parser`, `from gen_patch import fresh_uuid`) — `tools/patch/` stays flat; tests keep working via a `conftest.py` that prepends `tools/patch` to `sys.path`.
- `validate_snippet.py` resolves the `fmlint` package relative to its own directory — copy wrapper and package into the same parent (`tools/fmlint/`).
- Skill `name:` frontmatter must match SCOPE names (`fm-core`, `fm-connections`, `fm-xml`, `fm-patch`, `fm-proofkit`, `fm-docs`); `ddr` and `fm-scripts` carry over unchanged as skills 7–8 (distinct triggers — consistent with SCOPE's "merge by when they trigger" rule).
- Never modify vendored logic in this build — path/frontmatter edits only. Provenance notes go in `VENDOR.md` files.
- All new Python (doctor, docs-sync) gets a pytest test in `tests/`.
- Commit after every task; messages `feat(fm-dc): …` with the Claude co-author line.

---

### Task 1: Repo bootstrap

**Files:** Create `.claude-plugin/plugin.json`, `.gitignore`, `requirements.txt`, `README.md` (stub), `.venv/` (untracked).

**Produces:** installable plugin identity; `PY=.venv/bin/python` used by all later tasks.

- [ ] `python3 -m venv .venv && .venv/bin/pip -q install lxml pytest requests python-dotenv`
- [ ] `.claude-plugin/plugin.json`:

```json
{
  "name": "fm-dc",
  "version": "0.1.0",
  "description": "DataCraft agentic FileMaker development: SaXML patching with verify/rollback, DDR analysis, snippet validation, ProofKit and server-connection doctrine, project scaffolding.",
  "author": { "name": "Joe DaSilva / DataCraft Development", "email": "joe@datacraftdev.com" }
}
```

- [ ] `.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, `*.pyc`
- [ ] `requirements.txt`: `lxml`, `requests`, `python-dotenv`, `pytest`
- [ ] Verify: `.venv/bin/python -c "import lxml, json; json.load(open('.claude-plugin/plugin.json'))"` → exits 0
- [ ] Commit `feat(fm-dc): bootstrap plugin manifest and toolchain`

### Task 2: Vendor the patch engine + its test suite

**Files:** Create `tools/patch/` (fm_export.py, saxml_parser.py, saxml_diff.py, make_review.py, gen_patch.py, apply_patch.py, gen_scaffold.py, saxml_ignore.json, VENDOR.md), `tests/patch/` (all test_*.py + fixtures/ + setup_sandbox.sh + conftest.py).

**Interfaces — Produces:** CLI entry points later tasks reference: `tools/patch/fm_export.py`, `…/gen_patch.py`, `…/apply_patch.py`, `…/gen_scaffold.py`, `…/make_review.py`.

- [ ] Copy the seven modules + `saxml_ignore.json` from `FM-Patch-Agent/scripts/` → `tools/patch/` (no edits).
- [ ] Copy `FM-Patch-Agent/scripts/tests/` → `tests/patch/` (test files, `fixtures/`, `setup_sandbox.sh`; skip `__pycache__`). Check FM-Patch-Agent for an existing `conftest.py`/`pytest.ini` and replicate its path logic; otherwise create `tests/patch/conftest.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "patch"))
```

- [ ] `tools/patch/VENDOR.md`: source repo, commit/date, "logic unmodified; imports resolved via tests/patch/conftest.py".
- [ ] Run: `.venv/bin/python -m pytest tests/patch -q` → expect ~131 passed/skipped, 0 failures (Claris tools present, so E2E should run).
- [ ] Commit `feat(fm-dc): vendor FM-Patch-Agent patch engine with test suite`

### Task 3: Vendor the DDR engine and fmlint

**Files:** Create `tools/ddr/` (ddr.py, fmsaveasxml.py, readable.py, ddr_xml_utils.py, test_fmsaveasxml.py, VENDOR.md), `tools/fmlint/` (validate_snippet.py + `fmlint/` package, VENDOR.md pointer).

- [ ] Copy from `datacraft-Project-FM/scripts/`: the four ddr modules + test → `tools/ddr/`; `validate_snippet.py` + `fmlint/` → `tools/fmlint/`.
- [ ] Verify: `.venv/bin/python tools/ddr/ddr.py --help` exit 0; `.venv/bin/python tools/fmlint/validate_snippet.py --help` exit 0; `.venv/bin/python -m pytest tools/ddr -q` (skips allowed without exports).
- [ ] Commit `feat(fm-dc): vendor ddr engine and fmlint validator`

### Task 4: Skills — fm-core, fm-connections, ddr, fm-scripts

**Files:** Create `skills/fm-core/`, `skills/fm-connections/` (+`references/four-mode-doctrine.md`, `references/filemaker_integration_guide.md`, `references/filemaker_api_reference.md`, `scripts/fm_client.py`), `skills/ddr/`, `skills/fm-scripts/`.

- [ ] `cp -R` starter `.claude/skills/filemaker/` → `skills/fm-core/`; edit frontmatter `name: fm-core` (description unchanged).
- [ ] `cp -R` starter `.claude/skills/fm/` → `skills/fm-connections/`; edit `name: fm-connections`; add `scripts/fm_client.py` from starter `plugin/skills/client-filemaker/scripts/`; author `references/four-mode-doctrine.md` (the "Database Access — Four Modes" section + decision table, adapted from starter CLAUDE.md); copy the two reference docs from starter `docs/reference/`; add a short "References" section to SKILL.md pointing at them.
- [ ] `cp -R` `ddr/` and `fm-scripts/` skills unchanged (names stay `ddr`, `fm-scripts`); update any hardcoded `scripts/ddr.py` paths in their SKILL.md to `${CLAUDE_PLUGIN_ROOT}/tools/ddr/ddr.py` and `${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py`.
- [ ] Verify: `grep -r "scripts/ddr.py" skills/` returns nothing; each SKILL.md has valid frontmatter.
- [ ] Commit `feat(fm-dc): add fm-core, fm-connections, ddr, fm-scripts skills`

### Task 5: Skill — fm-xml (Kear merge)

**Files:** Create `skills/fm-xml/SKILL.md`, `skills/fm-xml/references/{snippets,layout,field}/` (each: GUIDE.md ← original SKILL.md + original references/ + README/VENDOR), `skills/fm-xml/references/ddr_xml_structure.md`, `references/ooe-source.md`.

- [ ] Copy each Kear skill dir into its subfolder; `mv SKILL.md GUIDE.md` inside each.
- [ ] Author `skills/fm-xml/SKILL.md`: frontmatter `name: fm-xml` with a description that unions the three Kear trigger descriptions (script XML / custom functions / layout objects / field definitions / fmxmlsnippet / SaXML grammar); body = router table (task → which GUIDE.md), the always-validate rule (`${CLAUDE_PLUGIN_ROOT}/tools/fmlint/validate_snippet.py` before any paste), and pointers to the grammar references.
- [ ] Verify frontmatter parses; router paths exist (`ls` each referenced file).
- [ ] Commit `feat(fm-dc): add fm-xml skill (merged Kear specs + grammar references)`

### Task 6: Skills — fm-patch, fm-proofkit, fm-docs

**Files:** Create `skills/fm-patch/` (SKILL.md + `references/patchability-matrix.md` + `references/workflows/{export-xml,diff-review,patch-apply,scaffold-file}.md`), `skills/fm-proofkit/` (SKILL.md + `references/proofkit.md` + `references/proofkit_webviewer_build.md`), `skills/fm-docs/` (SKILL.md + `references/claris-markdown-docs-reference.md`).

- [ ] Copy the reference files from FM-Patch-Agent `docs/` + `workflows/`, and starter `docs/reference|guides/`.
- [ ] Author `skills/fm-patch/SKILL.md`: triggers (patch/apply/deploy change to .fmp12, diff dev vs prod, rollback); pipeline map (export → parse → diff → review → gen_patch → apply → verify) with exact tool commands; tier gating rule (proven→patch, caution→`--allow-caution`+human ack, manual→clipboard via fm-xml or stop); project artifact conventions (`fm/fm-dc.json`, `fm/patches/<ts>/{before,after}/`, `fm/backups/`, `fm/changelog.md`); hand heavy transactions to the `fm-patch-builder` agent.
- [ ] Author `skills/fm-proofkit/SKILL.md`: triggers (ProofKit, webviewer, fmdapi/typegen/fmodata, MCP bridge); body = MCP-first rule (`connectedFiles` check), webviewer workflow-at-a-glance, package table, pointer to playbook.
- [ ] Author `skills/fm-docs/SKILL.md`: triggers (what does script step X do / exact option names / Claris doc lookups); local cache convention (`~/.fm-dc/docs-cache/` first), llms.txt URL pattern + redirect gotcha as fallback, `/fm-dc:fm-docs-sync` to build the mirror.
- [ ] Commit `feat(fm-dc): add fm-patch, fm-proofkit, fm-docs skills`

### Task 7: Docs mirror tool + command

**Files:** Create `tools/docs/sync_claris_docs.py`, `tests/test_sync_claris_docs.py`, `commands/fm-docs-sync.md`.

- [ ] Test first (`tests/test_sync_claris_docs.py`) — pure-logic tests, no network:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "docs"))
from sync_claris_docs import extract_urls, is_valid_page

def test_extract_urls_filters_by_docset():
    idx = ("https://help.claris.com/markdown/en/pro-help/foo.md\n"
           "https://help.claris.com/markdown/en/odata-guide/bar.md\n"
           "https://help.claris.com/markdown/ja/pro-help/baz.md\n")
    assert extract_urls(idx, ["pro-help"], locale="en") == ["https://help.claris.com/markdown/en/pro-help/foo.md"]

def test_is_valid_page_requires_frontmatter():
    assert is_valid_page("---\ntitle: x\n---\nbody")
    assert not is_valid_page("<!DOCTYPE html><html>404</html>")
```

- [ ] Implement `sync_claris_docs.py`: `extract_urls(index_text, docsets, locale)` (regex per the recipe in claris-markdown-docs-reference.md), `is_valid_page(text)` (starts with `---`), `main()` — fetch `llms-full.txt`, download each URL with `requests` following redirects, 0.2 s sleep, skip invalid pages, write to `~/.fm-dc/docs-cache/<docset>/<file>.md`, `--docsets` (default `pro-help,data-api-guide,odata-guide,app-upgrade-tool-guide,sql-reference`), `--dest`, `--limit` for smoke runs.
- [ ] `.venv/bin/python -m pytest tests/test_sync_claris_docs.py -q` → 2 passed.
- [ ] `commands/fm-docs-sync.md`: frontmatter `description: Build or refresh the local Claris documentation mirror`; body instructs running the tool via `${CLAUDE_PLUGIN_ROOT}/tools/docs/sync_claris_docs.py` and reporting page counts.
- [ ] Commit `feat(fm-dc): add Claris docs mirror tool and /fm-docs-sync`

### Task 8: Doctor tool

**Files:** Create `tools/doctor.py`, `tests/test_doctor.py`.

- [ ] Test first:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from doctor import run_checks

def test_run_checks_reports_all_categories():
    results = run_checks()
    names = {r["name"] for r in results}
    assert {"FMDeveloperTool", "FMUpgradeTool", "python-lxml", "env-file"} <= names
    assert all(isinstance(r["ok"], bool) for r in results)
```

- [ ] Implement `run_checks()` → list of `{"name", "ok", "detail"}`: shutil.which on the two Claris tools (also probe `/usr/local/bin`), importlib for lxml/requests, `.env` presence in cwd (ok=False is informative, not fatal); `main()` prints a table, exit 1 only if Claris tools missing.
- [ ] `pytest tests/test_doctor.py -q` → 1 passed. Commit `feat(fm-dc): add environment doctor`

### Task 9: Commands + scaffold template

**Files:** Create `commands/fm-init.md`, `commands/fm-scaffold.md`, `commands/fm-status.md`, `commands/fm-rollback.md`, `templates/scaffold/` (CLAUDE.md, `_pm/skeleton.md`, `_pm/TASKS.md`, `_pm/sessions/.gitkeep`, `schema/{ddrs,parsed,readable,reports}/.gitkeep`, `dev/.gitkeep`, `.env.example`, `.gitignore`).

- [ ] `fm-init.md`: run doctor → ask/confirm file path(s) + account env vars → write `fm/fm-dc.json` (`{"files":[{"path","account_env":"FM_DEV_USER","password_env":"FM_DEV_PASS"}]}`) → baseline export via `tools/patch/fm_export.py` into `fm/baseline/` → create `fm/patches/`, `fm/backups/`, seed `fm/changelog.md`. Mirrors SCOPE §5.3.
- [ ] `fm-scaffold.md`: copy `${CLAUDE_PLUGIN_ROOT}/templates/scaffold/` into cwd (minimized default); `--full` adds `webviewer/ web/ docs/` skeleton; `--client-kit` adds overlay skeleton copied from starter plugin structure (primer/connection/schema/glossary/recipes/guardrails stubs). Never overwrite existing files.
- [ ] `fm-status.md`: read `fm/fm-dc.json`, list baseline date, patches (each `fm/patches/<ts>/`), last changelog entries, backups.
- [ ] `fm-rollback.md`: list backups + patch before-states, confirm target, restore copy, append changelog entry, instruct re-export to confirm.
- [ ] Template files authored with DataCraft `_pm` conventions (skeleton = Wei Hao 5-step headers; TASKS = Current/Next/Waiting/Backlog; CLAUDE.md stub declares fm-dc plugin as capability source).
- [ ] Verify: frontmatter on all four commands; `templates/scaffold` tree matches list above.
- [ ] Commit `feat(fm-dc): add fm-init/fm-scaffold/fm-status/fm-rollback and scaffold template`

### Task 10: Agents

**Files:** Create `agents/fm-patch-builder.md`, `agents/fm-xml-validator.md`.

- [ ] Read `FM-Patch-Agent/workflows/patch-apply.md` + `export-xml.md` + `diff-review.md` in full; the agent prompts are those SOPs restructured, not paraphrased from memory.
- [ ] `fm-patch-builder.md`: frontmatter (`name`, `description` = when the main loop should delegate, `tools: Bash, Read, Grep, Glob, Write`); body = mission (apply an approved change set to a target .fmp12), the invariant sequence (export → gen_patch → backup → validatePatch → smoke → in-place → verify-by-re-export), tier rules, never-hand-edit-patch-XML rule, before/after state capture into `fm/patches/<ts>/`, changelog append, compact report contract (patch path, backup path, verify verdict, catalogs touched).
- [ ] `fm-xml-validator.md`: frontmatter with read-only tools + Bash; body = fmlint every snippet, scoped re-export + re-diff after patches (only touched catalogs), optional live checks via ProofKit MCP/Data API when reachable, verdict contract (pass/fail + evidence), explicit "you did not write this change; try to falsify it".
- [ ] Verify frontmatter parses; referenced tool paths exist.
- [ ] Commit `feat(fm-dc): add fm-patch-builder and fm-xml-validator agents`

### Task 11: Stubs, docs, final verification

**Files:** Create `tools/genobj/README.md` (Phase-3 stub: shape-catalog design pointer to SCOPE §6.2), `CLAUDE.md` (developing fm-dc), finalize `README.md` (install: `claude --plugin-dir`, quickstart, component map), `tests/prompt-battery.md` (seed ~10 prompts from SCOPE §8).

- [ ] Full suite: `.venv/bin/python -m pytest tests tools/ddr -q` → 0 failures.
- [ ] Structural check: every `skills/*/SKILL.md`, `commands/*.md`, `agents/*.md` has parseable frontmatter (script the check with python frontmatter split); `plugin.json` loads.
- [ ] Update `SCOPE.md` status line → `Approved 2026-07-06 — Phases 0–2 built; 3–4 pending`.
- [ ] Commit `feat(fm-dc): finalize plugin docs, stubs, and verification`

## Self-Review

- Spec coverage: SCOPE §5 components all mapped (6+2 skills → T4–6; agents → T10; tools → T2–3,7–8; commands+templates → T7,9; genobj stub → T11; overlay = `--client-kit` in T9). Phase 3–4 explicitly stubbed per goal.
- Placeholder scan: none; vendor tasks are complete instructions by nature (copy + exact edits).
- Type consistency: tool paths referenced in skills/commands/agents match T2–3 destinations; config filename `fm/fm-dc.json` consistent across T9 commands and T6 fm-patch skill.
