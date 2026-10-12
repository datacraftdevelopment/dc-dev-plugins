#!/usr/bin/env python3
"""The "lowered bar" scan: a plain diff scan, no model, run in finish() before the judge.

    python3 lowered_bar.py --repo <worktree> --base <base> --head <sha> [--check-cmd CMD] [--allow GLOB ...]

Catches a worker that got to green by weakening the checks instead of fixing the code: deleted or disabled
tests, new suppressions, a lowered threshold, an assert replaced by `pass`, a stub, an edit to the check itself.
Each hit is a finding {rule, file, line, hunk}. A scan that cannot run is itself a finding (rule "scan-error"),
never a clean pass. Prints the findings as JSON; exit 0 clean, 1 findings."""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

MAX_HUNK_LINES = 30
DOC_EXT = (".md", ".mdx", ".rst", ".txt")
CONFIG_EXT = (".toml", ".ini", ".cfg", ".json", ".yml", ".yaml")

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$|"
                       r"Tests?\.swift$|\.(test|spec)\.[jt]sx?$")
PY_TEST_DEF = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)|^\s*class\s+(\w+)")
SWIFT_TEST_DEF = re.compile(r"^\s*func\s+(\w+)")
JS_TEST_DEF = re.compile(r"^\s*(?:it|test)(?:\.each\([^)]*\))?\s*\(\s*['\"`]([^'\"`]+)")

SKIP = re.compile(r"@pytest\.mark\.(?:skip|skipif|xfail)|\bpytest\.(?:skip|xfail)\(|\bunittest\.skip|"
                  r"\bXCTSkip\b|\b(?:it|test|describe)\.skip\(|\bx(?:it|describe)\(|@Disabled\b")
SUPPRESSIONS = {
    # `noqa: E402` (import not at top, the sys.path idiom in tests) hides no defect, so it is not a suppression.
    "noqa": re.compile(r"#\s*noqa\b(?!\s*:\s*E402\s*$)"),
    "type-ignore": re.compile(r"#\s*type:\s*ignore"),
    "no-cover": re.compile(r"#\s*pragma:\s*no\s*cover"),
    "ts-ignore": re.compile(r"@ts-ig" r"nore"),
    "eslint-disable": re.compile(r"eslint-dis" r"able"),
    "swiftlint-disable": re.compile(r"swiftlint:dis" r"able"),
}
THRESHOLD = re.compile(r"""["']?([\w.-]*(?:fail[_-]?under|coverage|threshold|min[_-]?cov\w*|timeout)[\w.-]*)["']?\s*[:=]\s*["']?(\d+(?:\.\d+)?)""", re.I)
STUB = re.compile(r"\braise\s+NotImplementedError\b|\bTODO:\s*implement", re.I)
BODYLESS = {"pass", "...", "return", "return None"}
ASSERT = re.compile(r"^\s*(?:assert\b|self\.assert\w*\(|XCTAssert\w*\(|expect\()")
TRIVIAL_ASSERT = re.compile(r"^\s*(?:assert\s+(?:True|1)\s*$|pass\s*$|\.\.\.\s*$)")

CHECK_FILES = {"pytest.ini", "conftest.py", "tox.ini", "setup.cfg", ".coveragerc", "jest.config.js", "jest.config.ts",
               "vitest.config.ts", "vitest.config.js"}
CI_PATH = re.compile(r"^\.github/workflows/|^\.gitlab-ci\.ya?ml$|^\.circleci/|(^|/)Jenkinsfile$|^azure-pipelines\.ya?ml$")
TEST_SECTION = re.compile(r"^\s*\[(?:tool\.(?:pytest|coverage|tox)|pytest|coverage|tool:pytest)", re.I)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, errors="replace")


def parse_diff(text: str) -> list[dict]:
    """Files with status, paths and hunks. A hunk is {old, new, lines: [(kind, text, lineno)]}; kind is
    '+', '-' or ' ' and lineno is the new-file line for '+' and ' ', the old-file line for '-'."""
    files: list[dict] = []
    cur = hunk = None
    old_n = new_n = 0
    for raw in text.split("\n"):
        if raw.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", raw)
            cur = {"old": m.group(1) if m else "", "path": m.group(2) if m else "", "status": "M", "hunks": []}
            files.append(cur)
            hunk = None
        elif cur is None:
            continue
        elif hunk is None and raw.startswith("deleted file mode"):
            cur["status"] = "D"
        elif hunk is None and raw.startswith("new file mode"):
            cur["status"] = "A"
        elif hunk is None and raw.startswith("rename from "):
            cur["status"], cur["old"] = "R", raw[len("rename from "):]
        elif hunk is None and raw.startswith("rename to "):
            cur["path"] = raw[len("rename to "):]
        elif raw.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            if not m:
                continue
            old_n, new_n = int(m.group(1)), int(m.group(2))
            hunk = {"header": raw, "lines": []}
            cur["hunks"].append(hunk)
        elif hunk is not None and raw[:1] in ("+", "-", " ") and not raw.startswith(("+++ ", "--- ")):
            kind = raw[0]
            if kind == "-":
                hunk["lines"].append((kind, raw[1:], old_n))
                old_n += 1
            elif kind == "+":
                hunk["lines"].append((kind, raw[1:], new_n))
                new_n += 1
            else:
                hunk["lines"].append((kind, raw[1:], new_n))
                old_n += 1
                new_n += 1
    return files


def _hunk_text(hunk: dict) -> str:
    lines = [hunk["header"]] + [k + t for k, t, _ in hunk["lines"]]
    if len(lines) > MAX_HUNK_LINES:
        lines = lines[:MAX_HUNK_LINES] + [f"... ({len(lines) - MAX_HUNK_LINES} more diff lines)"]
    return "\n".join(lines)


def _is_test_path(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def _defs(path: str, text: str) -> str | None:
    """The name a line defines when it is a test-shaped definition for this file's language, else None."""
    if path.endswith(".py"):
        m = PY_TEST_DEF.match(text)
        return (m.group(1) or m.group(2)) if m else None
    if path.endswith(".swift"):
        m = SWIFT_TEST_DEF.match(text)
        return m.group(1) if m else None
    if re.search(r"\.[jt]sx?$", path):
        m = JS_TEST_DEF.match(text)
        return m.group(1) if m else None
    return None


def _collected(path: str, name: str) -> bool:
    """Would the runner still collect a definition with this name?"""
    if path.endswith(".py"):
        return name.startswith(("test", "Test"))
    if path.endswith(".swift"):
        return name.startswith("test")
    return True


def _is_test_name(path: str, name: str) -> bool:
    return _collected(path, name) if not re.search(r"\.[jt]sx?$", path) else True


class _Out:
    def __init__(self, allow):
        self.items: list[dict] = []
        self.allow = allow

    def add(self, rule, path, line, hunk, why=""):
        if any(fnmatch.fnmatch(path, g) for g in self.allow):
            return
        item = {"rule": rule, "file": path, "line": line, "hunk": _hunk_text(hunk) if isinstance(hunk, dict) else hunk}
        if why:
            item["why"] = why
        if not any((i["rule"], i["file"], i["line"]) == (rule, path, line) for i in self.items):
            self.items.append(item)


def _check_tokens(check_cmd: str) -> set[str]:
    try:
        toks = shlex.split(check_cmd or "")
    except ValueError:
        toks = (check_cmd or "").split()
    return {t[2:] if t.startswith("./") else t for t in toks if t and not t.startswith("-")}


def _pyproject_section(repo: Path, head: str, hunk: dict) -> bool:
    """True when a pyproject.toml hunk touches a test section (pytest, coverage, tox)."""
    shown = _git(repo, "show", f"{head}:pyproject.toml")
    if shown.returncode != 0:
        return True  # file gone or unreadable: it was edited and we can't tell where, so say so
    lines = shown.stdout.split("\n")
    for kind, _, n in hunk["lines"]:
        if kind == " ":
            continue
        for i in range(min(n, len(lines)) - 1, -1, -1):
            s = lines[i].strip()
            if s.startswith("["):
                if TEST_SECTION.match(s):
                    return True
                break
    return False


def scan_files(files: list[dict], check_cmd: str = "", allow=(), repo: Path | None = None, head: str = "") -> list[dict]:
    """Findings for a parsed diff. Pure apart from reading pyproject.toml at `head` for the section check."""
    out = _Out(tuple(allow or ()))
    tokens = _check_tokens(check_cmd)
    added_names = {(f["path"], n) for f in files for h in f["hunks"] for k, t, _ in h["lines"]
                   if k == "+" and (n := _defs(f["path"], t))}
    added_anywhere = {n for _, n in added_names}
    for f in files:
        path, old, status = f["path"], f["old"], f["status"]
        shown = path if status != "D" else old
        doc = shown.lower().endswith(DOC_EXT)
        is_test = _is_test_path(shown)

        # Edits to the check itself.
        base = shown.rsplit("/", 1)[-1]
        if shown in tokens or old in tokens:
            out.add("check-edited", shown, 1, f"the file `check_cmd` runs was {'deleted' if status == 'D' else 'changed'}")
        elif base in CHECK_FILES or CI_PATH.search(shown):
            out.add("check-edited", shown, 1, f"test config or CI workflow was {'deleted' if status == 'D' else 'changed'}")
        elif base == "pyproject.toml" and status != "D":
            for h in f["hunks"]:
                if repo is not None and _pyproject_section(repo, head, h):
                    out.add("check-edited", shown, next((n for _, _, n in h["lines"]), 1), h)
        elif base == "pyproject.toml":
            out.add("check-edited", shown, 1, "pyproject.toml was deleted")

        if status == "D":
            if is_test:
                out.add("deleted-test-file", shown, 1, "the test file was deleted")
            continue
        if doc:
            continue

        for h in f["hunks"]:
            lines = h["lines"]
            removed = [(t, n) for k, t, n in lines if k == "-"]
            added = [(t, n) for k, t, n in lines if k == "+"]

            # Removed or renamed-away tests. A removed definition paired with an added one in the same hunk is a
            # rename; it is only a finding if the new name is no longer collected.
            rem_defs = [(nm, n) for t, n in removed if (nm := _defs(old if status == "R" else path, t))]
            add_defs = [(nm, n) for t, n in added if (nm := _defs(path, t))]
            if is_test or rem_defs:
                spare = [d for d in add_defs if not any(d[0] == r[0] for r in rem_defs)]
                for nm, n in rem_defs:
                    if not _is_test_name(path, nm):
                        continue
                    if (path, nm) in added_names or (nm in added_anywhere):
                        continue  # still defined here, or moved
                    if spare:
                        new_nm, new_n = spare.pop(0)
                        if not _collected(path, new_nm) and _collected(path, nm):
                            out.add("test-disabled", path, new_n, h,
                                    f"`{nm}` was renamed to `{new_nm}`, which the runner no longer collects")
                        continue
                    if _collected(path, nm) or re.search(r"\.[jt]sx?$", path):
                        out.add("removed-test", path, n, h, f"`{nm}` was removed")

            for t, n in added:
                if SKIP.search(t):
                    out.add("test-skipped", path, n, h, "a test is newly skipped or disabled")
                if STUB.search(t) and not is_test:
                    out.add("stub", path, n, h, "a stub in shipped code")
            for kind, rx in SUPPRESSIONS.items():
                had = sum(1 for t, _ in removed if rx.search(t))
                new = [(t, n) for t, n in added if rx.search(t)]
                for t, n in new[had:]:
                    out.add("new-suppression", path, n, h, f"new `{kind}` suppression")

            # Weakened assertions: an assert line removed and a trivial line added in its place.
            rem_asserts = [n for t, n in removed if ASSERT.match(t)]
            triv = [n for t, n in added if TRIVIAL_ASSERT.match(t)]
            if rem_asserts and triv:
                out.add("weakened-assertion", path, triv[0], h, "an assertion was replaced by a no-op")

            # Lowered thresholds in config.
            if shown.lower().endswith(CONFIG_EXT):
                olds = {m.group(1).lower(): float(m.group(2)) for t, _ in removed if (m := THRESHOLD.search(t))}
                for t, n in added:
                    m = THRESHOLD.search(t)
                    if not m or m.group(1).lower() not in olds:
                        continue
                    key, new_v, old_v = m.group(1).lower(), float(m.group(2)), olds[m.group(1).lower()]
                    is_timeout = "timeout" in key
                    if (new_v > old_v) if is_timeout else (new_v < old_v):
                        out.add("lowered-threshold", path, n, h,
                                f"`{m.group(1)}` went from {old_v:g} to {new_v:g}" +
                                (" (a longer timeout lets a slow test pass)" if is_timeout else ""))

            # Stubs: real code replaced by an empty body.
            if not is_test:
                real_removed = [t for t, _ in removed if t.strip() and not t.strip().startswith(("#", "//"))]
                added_real = [(t.strip(), n) for t, n in added if t.strip()]
                if len(real_removed) >= 2 and added_real and all(
                        t in BODYLESS or STUB.search(t) or t.startswith("def ") or t.endswith(":")
                        for t, _ in added_real) and any(t in BODYLESS or STUB.search(t) for t, _ in added_real):
                    out.add("stub", path, added_real[0][1], h, "real code was replaced by an empty body")
    return out.items


def scan(repo, base: str, head: str, check_cmd: str = "", allow=()) -> list[dict]:
    """Findings for `git diff base...head`. Any failure to scan is returned as a finding, never as an empty list."""
    repo = Path(repo)
    try:
        r = _git(repo, "diff", "--no-color", "-M", "-U3", f"{base}...{head}")
    except (OSError, ValueError) as e:
        return [{"rule": "scan-error", "file": "", "line": 0, "hunk": f"could not run git diff: {e}"}]
    if r.returncode != 0:
        return [{"rule": "scan-error", "file": "", "line": 0,
                 "hunk": f"git diff {base}...{head} exited {r.returncode}: {(r.stderr or r.stdout).strip()[:300]}"}]
    try:
        return scan_files(parse_diff(r.stdout), check_cmd, allow, repo, head)
    except Exception as e:  # a scanner bug must fail the round, not pass it
        return [{"rule": "scan-error", "file": "", "line": 0, "hunk": f"the diff could not be scanned: {e!r}"}]


def finding_id(f: dict) -> str:
    return f"LB:{f['rule']}:{f['file']}:{f['line']}"


def finding_line(f: dict) -> str:
    where = f"{f['file']}:{f['line']}" if f["file"] else "(scan)"
    why = f" {f['why']}." if f.get("why") else ""
    return f"[{finding_id(f)}] lowered bar, {f['rule']} at {where}.{why}"


def section(findings: list[dict]) -> str:
    """The findings as a review section for the judge and the PR body."""
    out = ("\n\n### lowered-bar scan (deterministic diff scan, no model)\n"
           "Every hit below is BLOCKING. Clear one only when a done ticket's acceptance criteria explicitly call for "
           "that change, by listing its id in \"cleared\" with the criterion quoted verbatim. Do not repeat them in "
           "\"blocking\".\n")
    if not findings:
        return out + "No hits."
    return out + "\n".join(f"- {finding_line(f)}\n```diff\n{f['hunk']}\n```" for f in findings)


def apply_clearances(findings: list[dict], cleared, ticket_text: str) -> tuple[list[str], list[str]]:
    """(blocking lines, cleared lines). A hit is cleared only by a quote that appears verbatim in a done ticket's text.
    A scan error can never be cleared."""
    quotes = {}
    for c in cleared if isinstance(cleared, list) else []:
        if isinstance(c, dict) and c.get("id"):
            quotes[str(c["id"])] = " ".join(str(c.get("quote") or "").split())
    flat = " ".join((ticket_text or "").split())
    blocking, ok = [], []
    for f in findings:
        q = quotes.get(finding_id(f), "")
        if f["rule"] != "scan-error" and len(q) >= 8 and q in flat:
            ok.append(f"{finding_line(f)} Cleared by the ticket criterion: \"{q}\"")
        else:
            blocking.append(finding_line(f))
    return blocking, ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--check-cmd", default="")
    ap.add_argument("--allow", action="append", default=[])
    a = ap.parse_args(argv)
    found = scan(a.repo, a.base, a.head, a.check_cmd, a.allow)
    print(json.dumps(found, indent=2))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
