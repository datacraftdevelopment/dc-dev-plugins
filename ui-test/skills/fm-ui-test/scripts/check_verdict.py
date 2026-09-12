#!/usr/bin/env python3
"""Ringer check for the VERIFIER task.

The verifier reads the runner's receipt + artifacts and writes verdict.json.
This check enforces the verdict contract: every assertion in truth.json has a
per-assertion row with the verifier's OWN transcription and an artifact
reference; verdict is internally consistent (PASS only if every row passes);
a BLOCKED runner receipt can never become PASS. Exit 0 here is the product pass.

usage: check_verdict.py --truth truth.json [--receipt receipt.json] [--verdict verdict.json]
"""
import argparse, json, pathlib, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--receipt", default="receipt.json")
    ap.add_argument("--verdict", default="verdict.json")
    a = ap.parse_args()
    fails = []
    truth = json.loads(pathlib.Path(a.truth).read_text())
    vp = pathlib.Path(a.verdict)
    if not vp.exists(): print(f"FAIL: {vp} missing"); return 1
    try: v = json.loads(vp.read_text())
    except Exception as e: print(f"FAIL: {vp} not valid JSON: {e}"); return 1
    receipt = {}
    rp = pathlib.Path(a.receipt)
    if rp.exists():
        try: receipt = json.loads(rp.read_text())
        except Exception: fails.append("receipt.json unreadable by verifier check")
    verdict = v.get("verdict")
    if verdict not in ("PASS", "FAIL", "BLOCKED"): fails.append(f"verdict must be PASS|FAIL|BLOCKED, got {verdict!r}")
    if receipt.get("execution_outcome") == "BLOCKED" and verdict == "PASS":
        fails.append("runner receipt is BLOCKED; verdict PASS is impossible")
    rows = {row.get("id"): row for row in (v.get("per_assertion") or []) if isinstance(row, dict)}
    art_ids = {x.get("id") for x in (receipt.get("artifacts") or []) if isinstance(x, dict)}
    art_paths = {str(x.get("path")) for x in (receipt.get("artifacts") or []) if isinstance(x, dict)}
    for aid, spec in (truth.get("assertions") or {}).items():
        want = spec["expected"] if isinstance(spec, dict) else spec
        row = rows.get(aid)
        if not row: fails.append(f"assertion '{aid}' missing from per_assertion"); continue
        if "observed_by_verifier" not in row: fails.append(f"'{aid}': no observed_by_verifier — the verifier must transcribe, not copy")
        ref = row.get("artifact_ref")
        if not ref or (art_ids and ref not in art_ids and ref not in art_paths):
            fails.append(f"'{aid}': artifact_ref {ref!r} does not name a receipt artifact")
        res = row.get("result")
        if res not in ("pass", "fail"): fails.append(f"'{aid}': result must be pass|fail, got {res!r}"); continue
        seen = row.get("observed_by_verifier")
        if res == "pass" and str(seen).strip() != str(want):
            fails.append(f"'{aid}': marked pass but observed {seen!r} != expected {want!r}")
        if res == "fail" and str(seen).strip() == str(want):
            fails.append(f"'{aid}': marked fail but observed matches expected {want!r} — say why")
    if verdict == "PASS" and any(r.get("result") != "pass" for r in rows.values()):
        fails.append("verdict PASS with a failing per_assertion row")
    if verdict == "PASS" and rows and all(r.get("result") == "pass" for r in rows.values()) and len(rows) < len(truth.get("assertions") or {}):
        fails.append("verdict PASS but not every truth assertion has a row")
    if not v.get("basis"): fails.append("verdict.basis missing — state that screenshots/values were the basis, not runner notes")
    if fails:
        print("FAIL — verdict contract violations:"); [print(" -", f) for f in fails]; return 1
    print(f"{'PASS' if verdict == 'PASS' else 'FAIL'} — verifier verdict {verdict}: {len(rows)} assertion(s) transcribed against artifacts"
          + ("" if verdict == "PASS" else f"; disagreements={v.get('runner_disagreements')!r}"))
    return 0 if verdict == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
