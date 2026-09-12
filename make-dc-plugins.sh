#!/usr/bin/env bash
# make-dc-plugins.sh — re-cut dc-plugins (DataCraft's PUBLIC marketplace) from an
# rcc-fm checkout.
#
# Chain: fm-dc (private, here) --make-fm-rcc.sh--> fm-rcc (RCC-branded, public)
#        --this script--> dc-plugins/fm-dc + pm (DataCraft-credited, public).
#
# dc-plugins (public) is never hand-edited. It takes the already-debranded RCC tree
# (internal docs stripped, credentials scrubbed, DataCraft-as-methodology prose
# neutralized) and swaps the credit back: fm-rcc -> fm-dc (namespace AND data
# paths, the same blanket rename make-fm-rcc.sh does in reverse), RCC/Richard
# Carlton -> DataCraft Development, FMTrainingTV-AI/rcc-fm -> the dc-plugins
# marketplace. Every phrase-map entry must hit or the build aborts.
#
# Usage: ./make-dc-plugins.sh [--rcc <rcc-fm checkout>] [--dest <dc-plugins (public) checkout>]
#   defaults: ../rcc-plugins and ../dc-plugins relative to this script.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RCC="$HERE/../rcc-plugins"
DEST="$HERE/../dc-plugins"
while [ $# -gt 0 ]; do
  case "$1" in
    --rcc)  RCC="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
RCC="$(cd "$RCC" && pwd)"; DEST="$(cd "$DEST" && pwd)"
[ -d "$DEST/.git" ] || { echo "dest is not a git repo: $DEST" >&2; exit 1; }
[ -z "$(git -C "$DEST" status --porcelain)" ] || { echo "dest has uncommitted changes: $DEST" >&2; exit 1; }
RCC_COMMIT="$(git -C "$RCC" rev-parse --short HEAD)"
FM_VER="$(python3 -c "import json;print(json.load(open('$RCC/fm-rcc/.claude-plugin/plugin.json'))['version'])")"
PM_VER="$(python3 -c "import json;print(json.load(open('$RCC/pm/.claude-plugin/plugin.json'))['version'])")"
echo "== dc-plugins build: rcc-fm @ $RCC_COMMIT (fm-rcc $FM_VER, pm $PM_VER) -> $DEST"

# --- 1. fresh tree from the git-tracked rcc set ---------------------------------
BUILD="$(mktemp -d "${TMPDIR:-/tmp}/dc-plugins-build.XXXXXX")"
git -C "$RCC" archive HEAD | tar -x -C "$BUILD"
mv "$BUILD/fm-rcc" "$BUILD/fm-dc"

# --- 2. rebrand: exact phrase map, then global fm-rcc -> fm-dc token pass -------
BUILD="$BUILD" python3 <<'PYEOF'
import os, sys, pathlib
root = pathlib.Path(os.environ["BUILD"])
CREDIT_MD  = "Built by **Joe DaSilva** / **DataCraft Development**. © 2026 DataCraft Development"
EDITS = [
    (".claude-plugin/marketplace.json", '"name": "rcc-fm"', '"name": "dc-plugins"'),
    (".claude-plugin/marketplace.json",
     '"name": "Joe DaSilva",\n    "email": "digitaljoed@gmail.com"',
     '"name": "Joe DaSilva / DataCraft Development",\n    "email": "joe@datacraftdev.com"'),
    (".claude-plugin/marketplace.json", '"source": "./fm-rcc"', '"source": "./fm-dc"'),
    (".claude-plugin/marketplace.json", '"name": "fm-rcc"', '"name": "fm-dc"'),

    ("README.md", "# rcc-fm — RCC's Claude Code plugin marketplace",
                  "# dc-plugins — DataCraft's public Claude Code plugin marketplace"),
    ("README.md", "the project-management layer used in the workshop:",
                  "the project-management layer for agentic work:"),
    ("README.md", "/plugin marketplace add FMTrainingTV-AI/rcc-fm\n/plugin install fm-rcc",
                  "/plugin marketplace add datacraftdevelopment/dc-plugins\n/plugin install fm-dc"),
    ("README.md", "[fm-rcc/README.md](fm-rcc/README.md)", "[fm-dc/README.md](fm-dc/README.md)"),
    ("README.md", "Built by **Joe DaSilva** and **Richard Carlton**. © 2026 RCC — [MIT licensed](LICENSE).",
                  CREDIT_MD + " — [MIT licensed](LICENSE)."),

    ("LICENSE",       "Copyright (c) 2026 RCC", "Copyright (c) 2026 DataCraft Development"),
    ("fm-dc/LICENSE", "Copyright (c) 2026 RCC", "Copyright (c) 2026 DataCraft Development"),

    ("pm/.claude-plugin/plugin.json", '"name": "Joe DaSilva and Richard Carlton"',
                                      '"name": "Joe DaSilva / DataCraft Development"'),
    ("pm/README.md", "/plugin marketplace add FMTrainingTV-AI/rcc-fm",
                     "/plugin marketplace add datacraftdevelopment/dc-plugins"),
    ("pm/template/CLAUDE.md", "`FMTrainingTV-AI/rcc-fm`", "`datacraftdevelopment/dc-plugins`"),
    ("pm/template/README.md", "`FMTrainingTV-AI/rcc-fm`", "`datacraftdevelopment/dc-plugins`"),
    ("pm/SDLC.md", "the part the RCC course can render for an audience that has none of those tools.",
                   "the part a course can render for an audience that has none of those tools."),
    ("pm/SDLC.md", "The RCC course's bonus-SDLC page is an independent rendering",
                   "A companion course's bonus-SDLC page is an independent rendering"),

    ("fm-dc/.claude-plugin/plugin.json", '"name": "Joe DaSilva and Richard Carlton"',
                                         '"name": "Joe DaSilva / DataCraft Development"'),
    ("fm-dc/CLAUDE.md",
     "This plugin ships from the `FMTrainingTV-AI/rcc-fm` marketplace (plugin folder `fm-rcc/`).",
     "This plugin ships from the `datacraftdevelopment/dc-plugins` marketplace (plugin folder `fm-dc/`)."),
    ("fm-dc/README.md", "# fm-rcc — Agentic FileMaker Plugin", "# fm-dc — Agentic FileMaker Plugin"),
    ("fm-dc/README.md", "# from the rcc-fm marketplace\n/plugin marketplace add FMTrainingTV-AI/rcc-fm",
                        "# from the dc-plugins marketplace\n/plugin marketplace add datacraftdevelopment/dc-plugins"),
    ("fm-dc/README.md", "Built by **Joe DaSilva** and **Richard Carlton**. © 2026 RCC — MIT licensed, see [LICENSE](LICENSE).",
                        CREDIT_MD + " — MIT licensed, see [LICENSE](LICENSE)."),
]
failures = []
for rel, old, new in EDITS:
    p = root / rel
    text = p.read_text()
    if old not in text:
        failures.append(f"  NOT FOUND in {rel}: {old[:90]!r}")
        continue
    p.write_text(text.replace(old, new))
if failures:
    print("REBRAND MAP DRIFT — rcc text changed; update make-dc-plugins.sh:", file=sys.stderr)
    print("\n".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"phrase map: {len(EDITS)} edits applied")

for rel in ("pm/.claude-plugin/plugin.json", "fm-dc/.claude-plugin/plugin.json"):
    p = root / rel
    p.write_text(p.read_text().replace('"email": "digitaljoed@gmail.com"', '"email": "joe@datacraftdev.com"'))

# Blanket fm-rcc -> fm-dc (namespace, fm/fm-rcc.json -> fm/fm-dc.json, ~/.fm-rcc -> ~/.fm-dc).
# Safe only because the data paths rename together — same argument as make-fm-rcc.sh.
count = 0
for p in root.rglob("*"):
    if not p.is_file():
        continue
    raw = p.read_bytes()
    if b"\0" in raw[:8192]:
        continue
    if b"fm-rcc" in raw:
        p.write_bytes(raw.replace(b"fm-rcc", b"fm-dc")); count += 1
print(f"token pass: fm-rcc -> fm-dc in {count} files")
PYEOF
printf '.DS_Store\n/_pm/\n' > "$BUILD/.gitignore"

# --- 3. verification gate ---------------------------------------------------------
echo "== verify"
RESIDUE=$(grep -rIliE 'richard|carlton|FMTrainingTV|rcc-fm|fm-rcc|\bRCC\b' "$BUILD" || true)
[ -z "$RESIDUE" ] || { echo "RCC RESIDUE:"; echo "$RESIDUE"; exit 1; }
LINKS=$(find "$BUILD" -type l || true)
[ -z "$LINKS" ] || { echo "SYMLINKS:"; echo "$LINKS"; exit 1; }
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('$BUILD/**/.claude-plugin/*.json', recursive=True)]; print('manifests: valid JSON')"
echo "verify: clean"

# --- 4. replace the dest tree wholesale, commit ----------------------------------
git -C "$DEST" rm -rq . 2>/dev/null || true
git -C "$DEST" clean -fdxq
tar -C "$BUILD" -cf - . | tar -C "$DEST" -xf -
rm -rf "$BUILD"
cd "$DEST"
git add -A
if git diff --cached --quiet; then
  echo "== no changes; nothing to commit"
else
  git -c user.name="Joe DaSilva" -c user.email="joe@datacraftdev.com" commit -q -m "dc-plugins: fm-dc $FM_VER, pm $PM_VER (from rcc-fm @ $RCC_COMMIT)

Built by make-dc-plugins.sh — do not hand-edit this repo; change dc-plugins,
re-cut rcc-fm, then re-run.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
  echo "== committed: $(git log --oneline -1)"
fi
echo "== done (nothing pushed; push from $DEST when ready)"
