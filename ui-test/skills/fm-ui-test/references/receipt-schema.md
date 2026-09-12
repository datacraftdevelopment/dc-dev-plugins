# truth.json, receipt.json, verdict.json

## truth.json — written by the orchestrator BEFORE dispatch

```json
{
  "case_id": "invoice-post",
  "spec_sha256": "…",
  "assertions": {
    "status-rendered": {"expected": "Posted", "type": "rendered"},
    "dialog-text":     {"expected": "Invoice posted", "type": "dialog", "checkpoint": "dialog-shown"},
    "layout-after":    {"expected": "Invoices", "type": "state"}
  },
  "artifacts_required": ["evidence/invoice-post-before.png", "evidence/invoice-post-dialog.png", "evidence/invoice-post-after.png"],
  "min_png_bytes": 8000,
  "data_assertions": {"Invoices.Status where pk=1042": "Posted"}
}
```
`data_assertions` are checked by the orchestrator through the Data API, not by the runner.

## receipt.json — written by the runner

```json
{
  "schema_version": "1",
  "case_id": "invoice-post",
  "execution_outcome": "PASS-OBSERVED | FAIL | BLOCKED",
  "tool_used": "<exact tool / function names>",
  "read_method": "accessibility | pixels | mixed",
  "preconditions": [{"id": "current-record", "held": true, "evidence_ref": "a0"}],
  "actions": [{"seq": 1, "target": "Post button", "operation": "click", "performed_at": "UTC ISO"}],
  "observations": {
    "status-rendered": {"raw_text": "Posted", "source": "accessibility", "artifact_ref": "a2"},
    "dialog-text":     {"raw_text": "Invoice posted", "source": "accessibility", "artifact_ref": "a1"},
    "layout-after":    {"raw_text": "Invoices", "source": "accessibility", "artifact_ref": "a2"},
    "unreadable-example": {"raw_text": null, "source": "pixels", "reason": "field occluded by dialog", "artifact_ref": "a1"}
  },
  "artifacts": [
    {"id": "a0", "path": "evidence/invoice-post-before.png", "checkpoint": "before", "captured_at": "UTC ISO", "window_title": "Invoices"},
    {"id": "a1", "path": "evidence/invoice-post-dialog.png", "checkpoint": "dialog-shown", "captured_at": "…", "window_title": "Invoices"},
    {"id": "a2", "path": "evidence/invoice-post-after.png",  "checkpoint": "after", "captured_at": "…", "window_title": "Invoices"}
  ],
  "unexpected": [{"kind": "dialog", "raw_text": "…verbatim…", "artifact_ref": "a3"}],
  "mutations_made": false,
  "notes": "anything the tool said, verbatim",
  "blocker": {"stage": "precondition | locate_app | action | evidence", "code": "COMPUTER_USE_NOT_APPROVED | WINDOW_NOT_FOUND | LOGIN_FAILED | EVIDENCE_UNREADABLE | …", "reason": "…", "raw_error": "…verbatim…", "last_completed_action": 0}
}
```
`observations` may also be flat `{"id": "raw text"}` — `check_receipt.py` accepts both.

## verdict.json — written by the verifier

```json
{
  "case_id": "invoice-post",
  "verdict": "PASS | FAIL | BLOCKED",
  "per_assertion": [
    {"id": "status-rendered", "expected": "Posted", "observed_by_verifier": "Posted", "artifact_ref": "a2", "result": "pass"},
    {"id": "dialog-text", "expected": "Invoice posted", "observed_by_verifier": "Invoice posted.", "artifact_ref": "a1", "result": "fail", "note": "trailing period on screen"}
  ],
  "runner_disagreements": ["dialog-text: runner read 'Invoice posted', screenshot shows 'Invoice posted.'"],
  "basis": "screenshots and receipt values only; runner notes not used"
}
```
The verifier transcribes each artifact itself. `verdict` may be PASS only when every
`per_assertion.result` is `pass` and no assertion is missing.
