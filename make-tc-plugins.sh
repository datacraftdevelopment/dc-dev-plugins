#!/usr/bin/env bash
# make-tc-plugins.sh — re-cut tc-plugins (the TC Transcontinental edition) from
# DataCraft's PUBLIC marketplace tree.
#
# Chain: fm-dc (private) -> fm-rcc (make-fm-rcc.sh) -> dc-plugins public
#        (make-dc-plugins.sh) -> tc-plugins (this script).
#
# tc-plugins is never hand-edited. It is the public tree with the credit swapped
# (DataCraft Development -> Joe DaSilva, personal; marketplace named tc-plugins),
# plus a TC-only overlay taken from THIS private repo (decided 2026-10-04, so the
# RCC public edition stays as it is):
#   sdlc/                      the whole plugin (gate hooks, REVIEW.md, policy reviewer)
#   tc-overlay/pm/             WORKFLOW.md, the adversary-reviewer agent, the
#                              adversary-review and ship-acceptance skills
#   pm/scripts/session.py, pm/hooks/hooks.json   the private copies; pm takes the private version
#   minus pm's granola-transcript skill (TC does not use Granola, 2026-10-04)
# TC runs Claude Code only: no Ringer, no second vendor. The overlay's review is a
# fresh Claude subagent. Every phrase-map entry must hit or the build aborts.
#
# Usage: ./make-tc-plugins.sh [--src <public dc-plugins checkout>] [--dest <tc-plugins checkout>]
#   defaults: ../dc-plugins and ../tc-plugins relative to this script.
#   TC_REPO (env) — the marketplace source stamped into install lines. TC gets the
#   folder itself (no GitHub repo, decided 2026-10-04), so it defaults to a local path.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../dc-plugins"
DEST="$HERE/../tc-plugins"
TC_REPO="${TC_REPO:-/path/to/tc-plugins}"   # wherever TC puts the shared folder
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

# --- 2b. TC-only overlay from the private repo ------------------------------------
OVERLAY_PATHS="sdlc tc-overlay pm/scripts/session.py pm/hooks/hooks.json pm/.claude-plugin/plugin.json"
[ -z "$(git -C "$HERE" status --porcelain -- $OVERLAY_PATHS)" ] || { echo "uncommitted overlay sources in $HERE (commit first; the overlay is cut from HEAD)" >&2; exit 1; }
PRIV_COMMIT="$(git -C "$HERE" rev-parse --short HEAD)"
OV="$(mktemp -d "${TMPDIR:-/tmp}/tc-overlay.XXXXXX")"
git -C "$HERE" archive HEAD $OVERLAY_PATHS | tar -x -C "$OV"
BUILD="$BUILD" OV="$OV" TC_REPO="$TC_REPO" python3 <<'PYEOF'
import json, os, pathlib, shutil, sys
build = pathlib.Path(os.environ["BUILD"]); ov = pathlib.Path(os.environ["OV"]); repo = os.environ["TC_REPO"]
failures = []
def edit(rel, old, new):
    p = build / rel; text = p.read_text()
    if text.count(old) != 1:
        failures.append(f"  expected once, found {text.count(old)} in {rel}: {old[:90]!r}"); return
    p.write_text(text.replace(old, new))

# sdlc: the plugin as it is, minus its private README (rebuilt below from named sections)
shutil.copytree(ov / "sdlc", build / "sdlc")
src = (build / "sdlc/README.md").read_text()
def section(title):
    start = src.find(f"\n## {title}\n")
    if start < 0:
        failures.append(f"  sdlc/README.md: no section {title!r}"); return ""
    end = src.find("\n## ", start + 1)
    return src[start + 1: end if end > 0 else len(src)].rstrip() + "\n"
intro = src[: src.find("\n## ")].rstrip() + "\n"
proven = section("What has been proven")
cut = proven.find("Not proven:\n")
if cut < 0: failures.append("  sdlc/README.md: no 'Not proven:' list")
layout = section("Layout")
fence = layout.rfind("```")
readme = "\n".join([intro, section("What is in it"), section("Install"),
                    "## Not yet proven\n\n" + proven[cut + len("Not proven:\n"):].lstrip(),
                    section("Limits worth knowing"), layout[: fence + 3] + "\n"])
(build / "sdlc/README.md").write_text(readme)
edit("sdlc/README.md", "It uses Claude Code features only. No `pm`, Ringer or Codex dependency, so the\nsame kit works in a repo that has none of them.",
     "It uses Claude Code features only and does not depend on `pm`, so the same kit\nworks in a repo without it.")
edit("sdlc/README.md", "/plugin marketplace update dc-dev-plugins\n/plugin install sdlc@dc-dev-plugins",
     f"/plugin marketplace add {repo}\n/plugin install sdlc")
edit("sdlc/README.md", "Codex and other agents working in the same\n  repo, including Ringer workers on another engine, do not read these hooks.",
     "Other agents working in the same\n  repo do not read these hooks.")
edit("sdlc/skills/review-policy/SKILL.md",
     "Where a multi-seat review gate already runs, such as Ringer's `cross-review-gate`, keep that gate for the reviews it is chosen for and name `REVIEW.md` in its brief, so both tiers apply one policy.",
     "For a risky change, pm's `adversary-review` skill runs a hostile pass with its own subagent, and that reviewer reads this same `REVIEW.md`.")
edit("sdlc/.claude-plugin/plugin.json", "Uses only Claude Code features: no pm, Ringer or Codex dependency.",
     "Uses only Claude Code features and does not depend on pm.")
edit("sdlc/.claude-plugin/plugin.json", '"name": "Joe",', '"name": "Joe DaSilva",')

# pm: overlay files, the private session helper, the private version
shutil.copytree(ov / "tc-overlay/pm", build / "pm", dirs_exist_ok=True)
shutil.copy2(ov / "pm/scripts/session.py", build / "pm/scripts/session.py")
shutil.copy2(ov / "pm/hooks/hooks.json", build / "pm/hooks/hooks.json")
version = json.loads((ov / "pm/.claude-plugin/plugin.json").read_text())["version"]
manifest = build / "pm/.claude-plugin/plugin.json"; d = json.loads(manifest.read_text())
d["version"] = version
anchor = "Utility skills:"
if d["description"].count(anchor) != 1: failures.append("  pm plugin.json: description anchor 'Utility skills:' missing")
PM_ADD = ("adversary-review hands a risky change to a fresh read-only Claude subagent that tries to break it against its acceptance lines; "
          "ship-acceptance checks a deliverable against its accepted intent, by someone who did not build it, and records the evidence; ")
d["description"] = d["description"].replace(anchor, PM_ADD + anchor).replace(
    "SDLC.md is the portable doctrine layer — no tools named.", "SDLC.md is the doctrine; WORKFLOW.md binds it to these skills.")
manifest.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")

edit("pm/README.md", "**Read [`SDLC.md`](./SDLC.md) first** — the principles:",
     "**Read [`WORKFLOW.md`](./WORKFLOW.md) first** for how the skills fit together, then [`SDLC.md`](./SDLC.md) for the principles:")
edit("pm/README.md", "- **`okf`** skill *(utility)*",
     "- **`adversary-review`** skill and the **`adversary-reviewer`** agent — for a\n"
     "  risky change or a doubt the checks don't settle: a fresh, read-only Claude\n"
     "  subagent that did not write the change gets the diff, the acceptance lines\n"
     "  and the proof, and reports where the change fails them. It never edits and\n"
     "  never approves.\n"
     "- **`ship-acceptance`** skill — the last handoff: the accepted intent's\n"
     "  lines checked by someone who did not build it, a person releasing, and a\n"
     "  record in `docs/shipped/` that says blocked, ready-for-release, shipped or\n"
     "  released-with-exceptions as it actually is.\n"
     "- **`okf`** skill *(utility)*")
edit("pm/README.md", "├── commands/\n│   └── pm-scaffold.md       ← /pm:pm-scaffold\n",
     "├── agents/\n│   └── adversary-reviewer.md ← the read-only reviewer subagent\n├── commands/\n│   └── pm-scaffold.md       ← /pm:pm-scaffold\n")
edit("pm/README.md", "│   ├── sibling-sessions/ · verify-before-done/ · okf/ · granola-transcript/\n",
     "│   ├── sibling-sessions/ · verify-before-done/ · okf/\n│   ├── adversary-review/ · ship-acceptance/\n")

# TC does not use Granola: the skill and every mention of it come out
shutil.rmtree(build / "pm/skills/granola-transcript")
edit("pm/README.md",
     "- **`granola-transcript`** skill *(utility)* — fetches full verbatim Granola\n"
     "  meeting transcripts (list-then-match; the notes.granola.ai link id is not\n"
     "  the meeting id) and lands them in gitignored `_pm/transcripts/`.\n", "")
edit("pm/template/CLAUDE.md", "first transcript kept (e.g. `granola-transcript` skill)", "first transcript kept")
edit("pm/.claude-plugin/plugin.json",
     "Utility skills: okf (knowledge-bundle format) and granola-transcript (verbatim meeting transcripts into gitignored _pm/transcripts/).",
     "Utility skill: okf (knowledge-bundle format).")

# marketplace + root README
mp = build / ".claude-plugin/marketplace.json"; m = json.loads(mp.read_text())
names = [x["name"] for x in m["plugins"]]
if names != ["fm-dc", "pm"]: failures.append(f"  marketplace.json: expected [fm-dc, pm], found {names}")
for x in m["plugins"]:
    if x["name"] == "pm":
        x["description"] = x["description"].rstrip(".") + ("; adversary-review puts a fresh read-only Claude subagent on a risky change, "
                           "and ship-acceptance checks a deliverable against its accepted intent before and after release.")
m["plugins"].append({"name": "sdlc", "source": "./sdlc",
    "description": json.loads((build / "sdlc/.claude-plugin/plugin.json").read_text())["description"]})
mp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")

edit("README.md", "Two plugins for agentic development work.", "Three plugins for agentic development work. They run on Claude Code alone.")
edit("README.md", "credential-guard hook blocks staging credential-shaped files.\n",
     "credential-guard hook blocks staging credential-shaped files. `adversary-review`\n"
     "hands a risky change to a fresh Claude subagent that tries to break it, and\n"
     "`ship-acceptance` checks a deliverable against its accepted intent.\n\n"
     "**sdlc** — enforcement installed once per repo: `gate-hooks` puts a gate in the\n"
     "repo's `.claude/` (production commands, protected paths, a test lock for bug\n"
     "fixes), and `review-policy` sets up `REVIEW.md` with a read-only reviewer.\n")
edit("README.md", "/plugin install pm\n\n# one-time", "/plugin install pm\n/plugin install sdlc\n\n# one-time")
edit("README.md", "[pm/README.md](pm/README.md).", "[pm/README.md](pm/README.md) · [sdlc/README.md](sdlc/README.md).")

if failures:
    print("TC OVERLAY DRIFT — source text changed; update make-tc-plugins.sh:", file=sys.stderr)
    print("\n".join(failures), file=sys.stderr); sys.exit(1)
print(f"overlay: sdlc + pm additions applied (pm {version})")
PYEOF
rm -rf "$OV"
PM_VER="$(python3 -c "import json;print(json.load(open('$BUILD/pm/.claude-plugin/plugin.json'))['version'])")"
SDLC_VER="$(python3 -c "import json;print(json.load(open('$BUILD/sdlc/.claude-plugin/plugin.json'))['version'])")"

# --- 3. verification gate ---------------------------------------------------------
echo "== verify"
RESIDUE=$(grep -rIliE 'datacraft|richard|carlton|FMTrainingTV|rcc-fm|fm-rcc|\bRCC\b' "$BUILD" || true)
[ -z "$RESIDUE" ] || { echo "BRAND RESIDUE:"; echo "$RESIDUE"; exit 1; }
PRIVATE=$(grep -rIliE 'granola|ringer|\bastra\b|build-swarm|cross-review-gate|dc-autonomy|dc-dev-plugins|Agentic-Mini|_Core/' "$BUILD" || true)
[ -z "$PRIVATE" ] || { echo "PRIVATE-TOOLING RESIDUE (TC runs Claude Code only, and no Granola):"; echo "$PRIVATE"; exit 1; }
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
  git -c user.name="Joe DaSilva" -c user.email="digitaljoed@gmail.com" commit -q -m "tc-plugins: fm-dc $FM_VER, pm $PM_VER, sdlc $SDLC_VER (public @ $SRC_COMMIT + overlay @ $PRIV_COMMIT)

Built by make-tc-plugins.sh — do not hand-edit this repo; change dc-dev-plugins,
re-cut rcc-fm and dc-plugins, then re-run.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
  echo "== committed: $(git log --oneline -1)"
fi
echo "== done (nothing pushed; install coordinate stamped: $TC_REPO)"
