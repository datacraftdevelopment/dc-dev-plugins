#!/usr/bin/env python3
"""Ringer check for a UI-test RUNNER task.

Validates that receipt.json is a complete, honest execution record whose reads
match the orchestrator's truth.json. Exit 0 = the receipt is well-formed and
every asserted value matches. It is NOT the product verdict (see check_verdict.py).
A BLOCKED receipt fails on purpose so the blocker text lands in the retry prompt
and on the results page.

usage: check_receipt.py --truth truth.json [--receipt receipt.json]
"""
import argparse, json, pathlib, sys

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--receipt", default="receipt.json")
    a = ap.parse_args()
    fails = []
    truth = json.loads(pathlib.Path(a.truth).read_text())
    rp = pathlib.Path(a.receipt)
    if not rp.exists():
        print(f"FAIL: {rp} missing"); return 1
    try:
        r = json.loads(rp.read_text())
    except Exception as e:
        print(f"FAIL: {rp} is not valid JSON: {e}"); return 1

    out = r.get("execution_outcome")
    if out not in ("PASS-OBSERVED", "FAIL", "BLOCKED"):
        fails.append(f"execution_outcome must be PASS-OBSERVED|FAIL|BLOCKED, got {out!r}")
    if out == "BLOCKED":
        b = r.get("blocker") or {}
        print(f"FAIL: runner BLOCKED — stage={b.get('stage')!r} code={b.get('code')!r} "
              f"reason={b.get('reason')!r} raw_error={str(b.get('raw_error'))[:400]!r}")
        print("      (honest BLOCKED receipt; the test did not run — fix the blocker, reset, rerun)")
        return 1
    if truth.get("case_id") and r.get("case_id") != truth["case_id"]:
        fails.append(f"case_id {r.get('case_id')!r} != truth {truth['case_id']!r}")
    for k in ("tool_used", "read_method"):
        if not r.get(k): fails.append(f"receipt missing '{k}'")
    if r.get("read_method") not in (None, "accessibility", "pixels", "mixed"):
        fails.append(f"read_method must be accessibility|pixels|mixed, got {r.get('read_method')!r}")

    # artifacts: every required PNG exists, is a PNG, and is not a stub
    arts = {str(x.get("path")) for x in (r.get("artifacts") or []) if isinstance(x, dict)}
    min_bytes = int(truth.get("min_png_bytes", 8000))
    for req in truth.get("artifacts_required", []):
        if req not in arts: fails.append(f"required artifact {req} not listed in receipt.artifacts")
    for path in arts:
        p = pathlib.Path(path)
        if not p.exists(): fails.append(f"artifact {p} does not exist on disk"); continue
        data = p.read_bytes()
        if p.suffix.lower() == ".png" and data[:8] != PNG_MAGIC: fails.append(f"{p} is not a PNG (bad magic)")
        if len(data) < min_bytes: fails.append(f"{p} is {len(data)} bytes (<{min_bytes}) — not a real capture")

    # observations: flat {"id": "text"} or nested {"id": {"raw_text": ..., "source": ...}}
    obs = r.get("observations") or {}
    if not isinstance(obs, dict): fails.append("observations must be an object"); obs = {}
    def raw(v): return v.get("raw_text") if isinstance(v, dict) else v
    def src(v): return v.get("source") if isinstance(v, dict) else None
    for aid, spec in (truth.get("assertions") or {}).items():
        want = spec["expected"] if isinstance(spec, dict) else spec
        if aid not in obs: fails.append(f"assertion '{aid}' has no observation"); continue
        got = raw(obs[aid])
        if got is None:
            why = obs[aid].get("reason") if isinstance(obs[aid], dict) else None
            fails.append(f"assertion '{aid}' unreadable (reason={why!r}) — unreadable never passes"); continue
        if str(got).strip() != str(want):
            fails.append(f"assertion '{aid}': runner read {str(got)!r}, truth expects {want!r}")
        if isinstance(obs[aid], dict) and src(obs[aid]) not in ("accessibility", "pixels"):
            fails.append(f"assertion '{aid}': source must be accessibility|pixels")
    mm = r.get("mutations_made")
    if truth.get("mutations_allowed") is False and mm not in (False, None, [], "false", "none"):
        fails.append(f"receipt reports mutations {mm!r} but the case forbids them")
    if out == "FAIL" and not fails:
        fails.append("runner reported FAIL but every assertion matches truth — receipt must say which assertion failed")
    if fails:
        print("FAIL — receipt contract violations:"); [print(" -", f) for f in fails]; return 1
    print(f"PASS — receipt well-formed: {len(arts)} artifact(s) real, all {len(truth.get('assertions') or {})} "
          f"asserted reads match truth; tool={r.get('tool_used')!s:.80}; read_method={r.get('read_method')}")
    print("      (this is receipt validity, not the product verdict — see check_verdict.py)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
