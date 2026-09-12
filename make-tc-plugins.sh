#!/usr/bin/env bash
# make-tc-plugins.sh — re-cut tc-plugins (the TC Transcontinental edition) from
# DataCraft's PUBLIC marketplace tree.
#
# Chain: fm-dc (private) -> fm-rcc (make-fm-rcc.sh) -> dc-plugins public
#        (make-dc-plugins.sh) -> tc-plugins (this script).
#
# tc-plugins is never hand-edited. For now it is the public tree with the credit
# swapped: DataCraft Development -> Joe DaSilva (personal), the marketplace named
# tc-plugins, install coordinates pointing at the TC GitHub account. Plugin names
# (fm-dc, pm) and everything under them are untouched — a plain copy, as asked
# 2026-09-12. Every phrase-map entry must hit or the build aborts.
#
# Usage: ./make-tc-plugins.sh [--src <public dc-plugins checkout>] [--dest <tc-plugins checkout>]
#   defaults: ../dc-plugins and ../tc-plugins relative to this script.
#   TC_REPO (env) — the GitHub coordinate stamped into install lines.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../dc-plugins"
DEST="$HERE/../tc-plugins"
TC_REPO="${TC_REPO:-TC-GITHUB-ACCOUNT/tc-plugins}"   # set once the TC account is known
while [ $# -gt 0 ]; do
  case "$1" in
    --src)  SRC="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
SRC="$(cd "$SRC" && pwd)"
mkdir -p "$DEST"; DEST="$(cd "$DEST" && pwd)"
[ -d "$DEST/.git" ] || git -C "$DEST" init -q -b main
[ -z "$(git -C "$DEST" status --porcelain)" ] || { echo "dest has uncommitted changes: $DEST" >&2; exit 1; }
SRC_COMMIT="$(git -C "$SRC" rev-parse --short HEAD)"
FM_VER="$(python3 -c "import json;print(json.load(open('$SRC/fm-dc/.claude-plugin/plugin.json'))['version'])")"
PM_VER="$(python3 -c "import json;print(json.load(open('$SRC/pm/.claude-plugin/plugin.json'))['version'])")"
echo "== tc-plugins build: dc-plugins(public) @ $SRC_COMMIT (fm-dc $FM_VER, pm $PM_VER) -> $DEST"

# --- 1. fresh tree from the git-tracked public set ------------------------------
BUILD="$(mktemp -d "${TMPDIR:-/tmp}/tc-plugins-build.XXXXXX")"
git -C "$SRC" archive HEAD | tar -x -C "$BUILD"

# --- 2. rebrand: exact phrase map ------------------------------------------------
BUILD="$BUILD" TC_REPO="$TC_REPO" python3 <<'PYEOF'
import os, sys, pathlib
root = pathlib.Path(os.environ["BUILD"]); repo = os.environ["TC_REPO"]
CREDIT_MD = "Built by **Joe DaSilva**. © 2026 Joe DaSilva"
EDITS = [
    (".claude-plugin/marketplace.json", '"name": "dc-plugins"', '"name": "tc-plugins"'),
    (".claude-plugin/marketplace.json",
     '"name": "Joe DaSilva / DataCraft Development",\n    "email": "joe@datacraftdev.com"',
     '"name": "Joe DaSilva",\n    "email": "digitaljoed@gmail.com"'),

    ("README.md", "# dc-plugins — DataCraft's public Claude Code plugin marketplace",
                  "# tc-plugins — Claude Code plugins for TC Transcontinental"),
    ("README.md", "/plugin marketplace add datacraftdevelopment/dc-plugins", f"/plugin marketplace add {repo}"),
    ("README.md", "Built by **Joe DaSilva** / **DataCraft Development**. © 2026 DataCraft Development — [MIT licensed](LICENSE).",
                  CREDIT_MD + " — [MIT licensed](LICENSE)."),

    ("LICENSE",       "Copyright (c) 2026 DataCraft Development", "Copyright (c) 2026 Joe DaSilva"),
    ("fm-dc/LICENSE", "Copyright (c) 2026 DataCraft Development", "Copyright (c) 2026 Joe DaSilva"),

    ("pm/.claude-plugin/plugin.json", '"name": "Joe DaSilva / DataCraft Development"', '"name": "Joe DaSilva"'),
    ("pm/README.md", "/plugin marketplace add datacraftdevelopment/dc-plugins", f"/plugin marketplace add {repo}"),
    ("pm/template/CLAUDE.md", "`datacraftdevelopment/dc-plugins`", f"`{repo}`"),
    ("pm/template/README.md", "`datacraftdevelopment/dc-plugins`", f"`{repo}`"),

    ("fm-dc/.claude-plugin/plugin.json", '"name": "Joe DaSilva / DataCraft Development"', '"name": "Joe DaSilva"'),
    ("fm-dc/CLAUDE.md",
     "This plugin ships from the `datacraftdevelopment/dc-plugins` marketplace (plugin folder `fm-dc/`).",
     f"This plugin ships from the `{repo}` marketplace (plugin folder `fm-dc/`)."),
    ("fm-dc/README.md", "# from the dc-plugins marketplace\n/plugin marketplace add datacraftdevelopment/dc-plugins",
                        f"# from the tc-plugins marketplace\n/plugin marketplace add {repo}"),
    ("fm-dc/README.md", "Built by **Joe DaSilva** / **DataCraft Development**. © 2026 DataCraft Development — MIT licensed, see [LICENSE](LICENSE).",
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
    print("REBRAND MAP DRIFT — public text changed; update make-tc-plugins.sh:", file=sys.stderr)
    print("\n".join(failures), file=sys.stderr)
    sys.exit(1)
print(f"phrase map: {len(EDITS)} edits applied")
for rel in ("pm/.claude-plugin/plugin.json", "fm-dc/.claude-plugin/plugin.json"):
    p = root / rel
    p.write_text(p.read_text().replace('"email": "joe@datacraftdev.com"', '"email": "digitaljoed@gmail.com"'))
PYEOF

# --- 3. verification gate ---------------------------------------------------------
echo "== verify"
RESIDUE=$(grep -rIliE 'datacraft|richard|carlton|FMTrainingTV|rcc-fm|fm-rcc|\bRCC\b' "$BUILD" || true)
[ -z "$RESIDUE" ] || { echo "BRAND RESIDUE:"; echo "$RESIDUE"; exit 1; }
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
  git -c user.name="Joe DaSilva" -c user.email="digitaljoed@gmail.com" commit -q -m "tc-plugins: fm-dc $FM_VER, pm $PM_VER (from dc-plugins public @ $SRC_COMMIT)

Built by make-tc-plugins.sh — do not hand-edit this repo; change dc-dev-plugins,
re-cut rcc-fm and dc-plugins, then re-run.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
  echo "== committed: $(git log --oneline -1)"
fi
echo "== done (nothing pushed; install coordinate stamped: $TC_REPO)"
