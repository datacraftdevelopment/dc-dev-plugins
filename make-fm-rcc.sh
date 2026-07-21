#!/usr/bin/env bash
# make-fm-rcc.sh — build fm-rcc (the RCC-branded fork of fm-dc) as a build artifact.
#
# fm-rcc is never hand-edited: real fixes go into fm-dc here, then this script
# re-cuts the fork. It git-archives the tracked fm-dc set, strips internal docs,
# applies a deterministic rebrand map (every replacement must hit, or the build
# aborts — that's how upstream drift surfaces), renames the fm-dc data paths to
# fm-rcc ones, writes the new marketplace manifests + MIT LICENSE, verifies zero
# brand residue, runs the full test suite from the built tree, and (with --push)
# commits the result to github.com/FMTrainingTV-AI/rcc-fm.
#
# Naming: the REPO/marketplace is "rcc-fm" (fixed by the GitHub URL); the PLUGIN
# and everything it names (folder, /fm-rcc:* commands, fm/fm-rcc.json config,
# ~/.fm-rcc/ cache) is "fm-rcc".
#
# Usage: ./make-fm-rcc.sh [--push] [workdir]
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET_REPO="https://github.com/FMTrainingTV-AI/rcc-fm.git"
PUSH=0
WORK=""
for arg in "$@"; do
  case "$arg" in
    --push) PUSH=1 ;;
    *) WORK="$arg" ;;
  esac
done
[ -n "$WORK" ] || WORK="$(mktemp -d /tmp/rcc-fm-build.XXXXXX)"
REPO="$WORK/rcc-fm-repo"
PLUGIN="$REPO/fm-rcc"
UPSTREAM_COMMIT="$(git -C "$SRC" rev-parse --short HEAD)"
UPSTREAM_VERSION="$(python3 -c "import json;print(json.load(open('$SRC/fm-dc/.claude-plugin/plugin.json'))['version'])")"

echo "== fm-rcc build: fm-dc v$UPSTREAM_VERSION @ $UPSTREAM_COMMIT -> $REPO"

# --- 1. clone target, wipe working tree (true rebuild every run) ---------------
if [ ! -d "$REPO/.git" ]; then
  git clone "$TARGET_REPO" "$REPO" 2>/dev/null || { mkdir -p "$REPO" && git -C "$REPO" init -b main && git -C "$REPO" remote add origin "$TARGET_REPO"; }
fi
git -C "$REPO" config user.name "Joe DaSilva"
git -C "$REPO" config user.email "digitaljoed@gmail.com"
git -C "$REPO" rm -rq . 2>/dev/null || true
git -C "$REPO" clean -fdxq

# --- 2. import the git-tracked fm-dc set (never cp -R: .venv/sandbox stay behind)
mkdir -p "$PLUGIN"
git -C "$SRC" archive HEAD fm-dc | tar -x --strip-components=1 -C "$PLUGIN"

# --- 3. strip internal docs (DataCraft strategy / build history) ----------------
rm -f "$PLUGIN/SCOPE.md"
rm -rf "$PLUGIN/docs"

# --- 4. rebrand: exact phrase map, then global fm-dc -> rcc-fm token pass -------
PLUGIN="$PLUGIN" python3 <<'PYEOF'
import os, sys, pathlib

plugin = pathlib.Path(os.environ["PLUGIN"])

# (file, old, new) — every entry must match at least once or the build fails.
EDITS = [
    # plugin.json: de-brand description + author (Joe DaSilva keeps credit, company goes)
    (".claude-plugin/plugin.json",
     '"description": "DataCraft agentic FileMaker development:',
     '"description": "Agentic FileMaker development:'),
    (".claude-plugin/plugin.json",
     '"name": "Joe DaSilva / DataCraft Development"',
     '"name": "Joe DaSilva and Richard Carlton"'),
    (".claude-plugin/plugin.json",
     '"email": "joe@datacraftdev.com"',
     '"email": "digitaljoed@gmail.com"'),

    # README: title, dropped-doc links, install block, command table, status section
    ("README.md",
     "# fm-dc — DataCraft Agentic FileMaker Plugin",
     "# fm-rcc — Agentic FileMaker Plugin"),
    ("README.md",
     "> Why it exists and where it's going: [SCOPE.md](SCOPE.md). Working on the plugin itself: [CLAUDE.md](CLAUDE.md).",
     "> Working on the plugin itself: [CLAUDE.md](CLAUDE.md)."),
    ("README.md",
     "# from the dc-plugins marketplace",
     "# from the rcc-fm marketplace"),
    ("README.md",
     "/plugin marketplace add datacraftdevelopment/dc-plugins",
     "/plugin marketplace add FMTrainingTV-AI/rcc-fm"),
    ("README.md",
     "Lay down the DataCraft project structure without adopting a file.",
     "Lay down the standard project structure without adopting a file."),
    ("README.md",
     "Phases 0–2 of [SCOPE.md](SCOPE.md) are built (tools vendored + tested, agents + commands live). The v0.4.0 skill refactor split the pack into **one verb per skill** (see [`docs/superpowers/plans/2026-07-09-skill-refactor.md`](docs/superpowers/plans/2026-07-09-skill-refactor.md)). v0.6.0 opened the **hosted-file lane**: the `fm-admin` server door (Admin API download), the `xml_to_fmp12` XML→file converter, and a scaffold that ships the remote-export toolbelt + numbered runbooks. Next: Phase 3 (deterministic `genobj` shape compiler, fuller docs cache, prompt battery) and the rest of Phase 4 (`/fm-client-kit` generator, schema-builder agent) — see SCOPE §9.",
     "Tools are vendored and tested, agents and commands are live, and the skill pack is organized as **one verb per skill**. v0.6.0 opened the **hosted-file lane**: the `fm-admin` server door (Admin API download), the `xml_to_fmp12` XML→file converter, and a scaffold that ships the remote-export toolbelt + numbered runbooks. Planned next: a deterministic `genobj` shape compiler, a fuller docs cache, and a `/fm-client-kit` generator."),

    # Plugin dev guide: drop SCOPE refs, de-brand clean-room rule, repoint marketplace
    ("CLAUDE.md",
     "(see [SCOPE.md](SCOPE.md) for what/why, [README.md](README.md) for install/use)",
     "(see [README.md](README.md) for install/use)"),
    ("CLAUDE.md",
     "**Clean-room rule** (SCOPE §10): nothing in this repo may be copied from Claris's beta toolkit plugin. DataCraft code + public docs only.",
     "**Clean-room rule:** nothing in this repo may be copied from Claris's beta toolkit plugin. Original code + public docs only."),
    ("CLAUDE.md",
     "- Phase roadmap and open questions live in SCOPE.md §9/§11 — check them before starting new work.\n",
     ""),
    ("CLAUDE.md",
     "This plugin ships from the `dc-plugins` marketplace (`dc-plugins/fm-dc/`).",
     "This plugin ships from the `FMTrainingTV-AI/rcc-fm` marketplace (plugin folder `fm-rcc/`)."),

    # Commands: company-as-methodology phrases -> neutral
    ("commands/fm-init.md",
     " Mirrors the shape of Claris's `/filemaker-init`, using the DataCraft pipeline.",
     ""),
    ("commands/fm-init.md",
     "lay down the minimized DataCraft structure — don't ask, just do it.",
     "lay down the minimized project structure — don't ask, just do it."),
    ("commands/fm-scaffold.md",
     "description: Scaffold a DataCraft FileMaker project folder",
     "description: Scaffold a FileMaker project folder"),
    ("commands/fm-scaffold.md",
     "Scaffold the DataCraft project structure into the current directory",
     "Scaffold the standard project structure into the current directory"),
    ("commands/fm-scaffold.md",
     "per the DataCraft client-kit model",
     "per the client-kit overlay model"),

    # fm/ tree diagram: rename the config with spacing adjusted so the arrow
    # column stays aligned (fm-rcc.json is one char longer than fm-dc.json)
    ("skills/fm-patch/SKILL.md",
     "fm-dc.json        ←",
     "fm-rcc.json       ←"),

    # Tests doc
    ("tests/prompt-battery.md",
     "The trusted-suite idea at DataCraft scale (SCOPE §8): run these",
     "The trusted-suite idea: run these"),

    # Vendored-code provenance: keep the facts, drop brand + machine paths
    ("tools/ddr/VENDOR.md",
     "# Vendored: DataCraft DDR / Save-as-XML analysis engine",
     "# Vendored: DDR / Save-as-XML analysis engine"),
    ("tools/ddr/VENDOR.md",
     "- **Source:** `/Users/joe/Dropbox/_Bots/_starters/datacraft-Project-FM/scripts/` (synced there 2026-07-02 from `_agentic-2026/_library/skills/core-infrastructure/filemaker-ddr`)",
     "- **Source:** the author's prior FileMaker DDR analysis toolkit (private upstream, synced 2026-07-02)"),
    ("tools/patch/VENDOR.md",
     "- **Source:** `/Users/joe/Dropbox/DC_Code/_RCC/FM-Patch-Agent` (private repo), commit `adf7c1d` (2026-06-14)",
     "- **Source:** FM-Patch-Agent (private upstream repo), commit `adf7c1d` (2026-06-14)"),
    ("tools/genobj/README.md",
     "This tool closes that gap, per [SCOPE.md](../../SCOPE.md) §6.2:",
     "This tool closes that gap:"),
    ("tools/genobj/README.md",
     "original DataCraft-authored content, redistributable",
     "original content, redistributable"),
    ("tools/genobj/README.md",
     "with `ddr.py` — SCOPE open question #4)",
     "with `ddr.py`)"),

    # Private-infrastructure residue in shipped skill text
    ("skills/fm-saxml/SKILL.md",
     "> Engine provenance: synced from Joe's library skill `_agentic-2026/_library/skills/core-infrastructure/filemaker-ddr` (2026-07-02). When improving the engine, update the library copy too — or make this starter's copy the one true home and retire the library's.",
     "> Engine provenance: vendored 2026-07-06 — see `tools/ddr/VENDOR.md`."),
    ("skills/fm-odata/SKILL.md",
     "(e.g. `JDAI`, `SPAI`, `LEADGEN`)",
     "(e.g. `CONN_A`, `CONN_B`)"),
    ("skills/fm-odata/references/odata-lessons.md",
     "(`JDAI`, `SPAI`, `LEADGEN`, `SBSOS`)",
     "(e.g. `CONN_A`, `CONN_B`, `CONN_C`)"),
    ("skills/fm-odata/references/odata-lessons.md",
     "- The closest-named (`SPAI`) resolved to a database called `StartingPoint_AI_FM22`, and its stored credentials returned",
     "- The closest-named ID resolved to a *different* database entirely, and its stored credentials returned"),

    # Real-looking credentials in a docstring -> placeholders
    ("skills/fm-odata/scripts/odata_client.py",
     "server  - agentic-workshop.atrcc.com",
     "server  - your-server.example.com"),
    ("skills/fm-odata/scripts/odata_client.py",
     "file    - AI_RC_SP_24_Lite.fmp12",
     "file    - YourFile.fmp12"),
    ("skills/fm-odata/scripts/odata_client.py",
     "account - api\n",
     "account - apiuser\n"),
    ("skills/fm-odata/scripts/odata_client.py",
     "pass    - api!234",
     "pass    - your-password"),

    # Scaffold template: drop the dangling cross-plugin `whats-next` dependency
    ("templates/scaffold/_pm/skeleton.md",
     "the `whats-next` skill reads this when proposing what to pick up. New requests get compared to it",
     "re-read this when deciding what to pick up next. New requests get compared to it"),
]

failures = []
for rel, old, new in EDITS:
    p = plugin / rel
    text = p.read_text()
    if old not in text:
        failures.append(f"  NOT FOUND in {rel}: {old[:90]!r}")
        continue
    p.write_text(text.replace(old, new))
if failures:
    print("REBRAND MAP DRIFT — upstream text changed; update make-rcc-fm.sh:", file=sys.stderr)
    print("\n".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"phrase map: {len(EDITS)} edits applied")

# Global token pass: fm-dc -> fm-rcc everywhere (namespace, data paths
# fm/fm-dc.json -> fm/fm-rcc.json and ~/.fm-dc -> ~/.fm-rcc, prose). Safe as a
# blanket rename ONLY because the fork renames the data paths too.
count = 0
for p in plugin.rglob("*"):
    if not p.is_file():
        continue
    raw = p.read_bytes()
    if b"\0" in raw[:8192]:  # binary (.fmp12, .gz)
        continue
    if b"fm-dc" in raw:
        p.write_bytes(raw.replace(b"fm-dc", b"fm-rcc"))
        count += 1
print(f"token pass: fm-dc -> fm-rcc in {count} files")

# Credit + license note at the end of the plugin README
readme = plugin / "README.md"
readme.write_text(readme.read_text().rstrip() + "\n\n---\n\nBuilt by **Joe DaSilva** and **Richard Carlton**. © 2026 RCC — MIT licensed, see [LICENSE](LICENSE).\n")
PYEOF

# --- 5. marketplace manifest, LICENSE, root README, root .gitignore -------------
mkdir -p "$REPO/.claude-plugin"
PLUGIN_DESC="$(python3 -c "import json;print(json.load(open('$PLUGIN/.claude-plugin/plugin.json'))['description'])")"
python3 - "$REPO/.claude-plugin/marketplace.json" "$PLUGIN_DESC" <<'PYEOF'
import json, sys
path, desc = sys.argv[1], sys.argv[2]
json.dump({
    "name": "rcc-fm",
    "owner": {"name": "Joe DaSilva", "email": "digitaljoed@gmail.com"},
    "plugins": [{"name": "fm-rcc", "source": "./fm-rcc", "description": desc}],
}, open(path, "w"), indent=2)
open(path, "a").write("\n")
PYEOF

cat > "$REPO/LICENSE" <<'EOF'
MIT License

Copyright (c) 2026 RCC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF
cp "$REPO/LICENSE" "$PLUGIN/LICENSE"   # travels with the installed plugin

cat > "$REPO/README.md" <<'EOF'
# rcc-fm — RCC's Claude Code plugin marketplace

Home of **fm-rcc**, a Claude Code plugin for agentic FileMaker development:
calculation language, paste-ready validated XML, Save-as-XML/DDR schema
analysis, and safe `.fmp12` patching (backup → validate → verify → rollback),
plus Data API / OData / ProofKit integration and offline Claris docs lookup.

## Install

```bash
/plugin marketplace add FMTrainingTV-AI/rcc-fm
/plugin install fm-rcc

# one-time per machine — the tools run on system python3
pip3 install lxml requests python-dotenv
```

Full documentation: [fm-rcc/README.md](fm-rcc/README.md).

---

Built by **Joe DaSilva** and **Richard Carlton**. © 2026 RCC — [MIT licensed](LICENSE).
EOF

printf '.DS_Store\n' > "$REPO/.gitignore"

# --- 6. verification gate: zero brand/leak residue, valid manifests, no symlinks
echo "== verify"
RESIDUE=$(grep -rIlie 'datacraft|data craft|dc-plugins|datacraftdev|DC_Code|atrcc\.com|api!234|JDAI|SPAI|LEADGEN|SBSOS|_agentic-2026|/Users/' "$PLUGIN" || true)
[ -z "$RESIDUE" ] || { echo "BRAND/LEAK RESIDUE:"; echo "$RESIDUE"; exit 1; }
TOKEN=$(grep -rIl 'fm-dc' "$PLUGIN" || true)
[ -z "$TOKEN" ] || { echo "fm-dc TOKEN RESIDUE:"; echo "$TOKEN"; exit 1; }
LINKS=$(find "$REPO" -type l | grep -v '\.git/' || true)
[ -z "$LINKS" ] || { echo "SYMLINKS:"; echo "$LINKS"; exit 1; }
python3 -c "import json; json.load(open('$REPO/.claude-plugin/marketplace.json')); json.load(open('$PLUGIN/.claude-plugin/plugin.json')); print('manifests: valid JSON')"
echo "verify: clean (no brand residue, no fm-dc tokens, no symlinks)"

# --- 7. test suite from the built tree (pre-flight #7: parity proof) ------------
echo "== test suite"
( cd "$PLUGIN" \
  && python3 -m venv .venv \
  && .venv/bin/pip install -q -r requirements.txt \
  && bash tests/patch/setup_sandbox.sh >/dev/null \
  && .venv/bin/python -m pytest tests -q )

# --- 8. commit (and push with --push) -------------------------------------------
cd "$REPO"
git add -A
if git diff --cached --quiet; then
  echo "== no changes vs target repo; nothing to commit"
else
  git commit -q -m "fm-rcc v$UPSTREAM_VERSION: synced from upstream v$UPSTREAM_VERSION @ $UPSTREAM_COMMIT

Built by make-fm-rcc.sh — do not hand-edit this repo; change upstream and re-run.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  echo "== committed: $(git log --oneline -1)"
fi
if [ "$PUSH" = 1 ]; then
  git push -u origin main
  echo "== pushed to $TARGET_REPO"
else
  echo "== dry run (no --push). Repo ready at: $REPO"
fi
