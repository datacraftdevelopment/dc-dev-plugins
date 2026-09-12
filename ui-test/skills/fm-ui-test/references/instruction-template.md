# Test instruction template (runner spec)

Open every runner spec with the Ringer worker preamble (see the `ringer` skill),
then this. Replace every `<…>`. Keep it self-contained — the worker cannot ask.

```
ROLE: You are the UI test RUNNER for one FileMaker test case. You perform the
steps below in FileMaker Pro using your computer-use tool, capture evidence, and
write ./receipt.json. You do not judge pass/fail: report what you observed.
You own only ./receipt.json and ./evidence/. Touch nothing else on disk.

CASE: <case_id>  (spec digest: <sha256 of this spec, filled by the manifest writer>)

PRECONDITIONS (verify each and record evidence before acting; if any fails,
stop and write a BLOCKED receipt with stage "precondition"):
- FileMaker Pro window titled "<file window title>" is open; no dialog showing.
- Layout: "<layout>"  Mode: Browse  View: Form
- Record with <primary key field> = "<pk>" is the current record.
- Signed in as account "<account>" (privilege set "<set>").
- Field "<field>" currently shows "<initial value>"   ← proves the action does something

ACTION (one step per line; do exactly this, nothing else):
1. <click / menu path / type — target named exactly as labelled on screen>
2. <…>

ASSERTIONS (read each and record raw_text + source). Every `expected` is a
literal string the orchestrator computed when writing this spec — "today's
date" is written as the exact rendered text, e.g. "9/12/2026", never as a rule:
- id: <status-rendered>  type: rendered  target: field "Status"  expected: "Posted"
- id: <dialog-text>      type: dialog    expected: "Invoice posted"  checkpoint: dialog-shown
- id: <layout-after>     type: state     target: layout pop-up  expected: "Invoices"

FAILURE SIGNATURES (report these as FAIL with evidence, do not work around them):
- dialog did not appear within 10 s
- Status still shows the initial value
- an unexpected dialog or error appeared — capture it and record its text verbatim

EVIDENCE REQUIRED:
- ./evidence/<case_id>-before.png   (window capture before step 1)
- ./evidence/<case_id>-dialog.png   (while the dialog is showing)
- ./evidence/<case_id>-after.png    (after the last step)
Captures are the "<file window title>" window only. PNG. Real pixels.

HARD RULES: perform each action at most once; never click "<mutating button>"
twice; never type into any field not named above; never fix, retry, or work
around anything — report it; never dismiss a dialog other than the expected
one; if computer use is not approved for FileMaker Pro, write a BLOCKED receipt
with the verbatim error and stop.

OUTPUT: ./receipt.json exactly per the receipt schema. Every observation carries
raw_text (or null + reason) and source ∈ {accessibility, pixels}. Outcome is
PASS-OBSERVED only if every assertion was read and matched your own read;
FAIL if any read contradicts; BLOCKED if you could not run or could not read.
```
