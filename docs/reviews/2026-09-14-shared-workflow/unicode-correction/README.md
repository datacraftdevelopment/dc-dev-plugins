# Unicode policy-label correction — independent Astra worker

Completed 2026-09-14. Independently confirmed only Finding 1 in `/Users/joe/Documents/Codex/2026-09-13/users-joe-agentic-mini-core-plugins/work/workflow-implementation/review-claude-closure.md`, then minimally corrected it. No delegation or questions.

## Independent before/after proof

Inspected canonical `agreement_contract.locate`, runtime `agreement.load`, the sync script, both existing boundary regression files, and the PM evidence/contract fixtures. The attempted-label separator was `[ \t]+`, so Unicode separators were returned as genuine absence. Canonical acceptance and attempted-heading prefix rules are separate, unchanged checks.

Before any source edit, ran the real PM `acceptance.py --record <temp record.json> --intent <temp intent.md>` subprocess via the existing `EvidenceChannelCliTests.run_cli` fixture. For each label, removed evidence requirements and channels from the record using the existing `legacy_record()` helper. For Execution agreement, retained the valid approved agreement and omitted the requirements section; for Evidence requirements, retained the requirements section and omitted the agreement. Changed only the space between label words.

| Label | Separator | Before | After |
|---|---|---|---|
| Execution agreement | NBSP U+00A0 | exit 0, shipped | exit 2, blocked |
| Execution agreement | en space U+2002 | exit 0, shipped | exit 2, blocked |
| Execution agreement | ideographic space U+3000 | exit 0, shipped | exit 2, blocked |
| Evidence requirements | NBSP U+00A0 | exit 0, shipped | exit 2, blocked |
| Evidence requirements | en space U+2002 | exit 0, shipped | exit 2, blocked |
| Evidence requirements | ideographic space U+3000 | exit 0, shipped | exit 2, blocked |
| Both labels (4 cases) | double ASCII space / tab | exit 2, blocked | exit 2, blocked |

Each after refusal names the relevant canonical heading: `expected exactly one ## Execution agreement heading` or `expected exactly one ## Evidence requirements heading`. Full actual CLI stdout/stderr and exit codes: [before-cli.log](before-cli.log), [after-cli.log](after-cli.log). Both probe batches used `RINGER_NO_SELF_UPDATE=1 RINGER_NO_CATALOG_REFRESH=1 PYTHONDONTWRITEBYTECODE=1 python3 -` with inline Python importing the existing fixture and iterating the two labels × five separators. Their subprocess entry point was the actual acceptance CLI; no validator mock was used.

Extended the existing test parameter cases before editing production code. The red run returned exit 1: **9 tests, exactly 6 failed Unicode subcases**, each `AssertionError: 0 != 2` with `status: shipped`. Canonical headings, legacy absence, topic titles, scalar identities, and ASCII cases passed during that run. [Full red output](red-boundary.log).

## Exact scope and diff

Only these four source/test files were edited (all other new artifacts are in this worker directory):

- `/Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts/agreement_contract.py`
- `/Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts/test_review_boundary_variants.py`
- `/Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/pm/scripts/agreement_contract.py`
- `/Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/tests/test_review_boundary_variants.py`

Production change: join attempted-label words with `[^\S\r\n]+` instead of `[ \t]+`. This includes Unicode whitespace while excluding CR/LF. The anchored heading-prefix restriction and exact canonical equality check are byte-unchanged: this broadens rejection of malformed labels, never approval. The existing runtime whitespace tuple gained three Execution agreement variants; both existing PM whitespace tuples gained NBSP/en-space/ideographic-space. No baseline test or lead probe was edited.

PM was resynced exclusively through `scripts/sync_execution_contract.py`, not hand-edited. Both contracts now have SHA-256 `9f41dfc54df2d8971f386a53bd9cb18ebbef4be92e45ef71c19b3d32b0ac7e28`. [Before manifest](before-files.json), [after manifest](after-files.json), [exact worker diff](owned.diff). Snapshots predate the worker's edits and preserve the session's existing changes.

```diff
--- /Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts/agreement_contract.py (before)
+++ /Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts/agreement_contract.py (after)
@@ -145,7 +145,7 @@
     exists and it is exactly `## <heading>`, this raises rather than letting a
     near-miss select legacy behavior."""
     masked = mask_fences(text)
-    label = r'[ \t]+'.join(re.escape(word) for word in heading.split())
+    label = r'[^\S\r\n]+'.join(re.escape(word) for word in heading.split())
     attempts = list(re.finditer(r'^ {0,3}#{1,6}[ \t]*' + label
                                 + r'\b[^\n]*$', masked, re.M | re.I))
     if not attempts:
--- /Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts/test_review_boundary_variants.py (before)
+++ /Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts/test_review_boundary_variants.py (after)
@@ -179,7 +179,8 @@
 
     def test_whitespace_variants_fail_closed(self):
         import agreement
-        for heading in ('Execution  agreement', 'Execution\tagreement', 'Execution   agreement'):
+        for heading in ('Execution  agreement', 'Execution\tagreement', 'Execution   agreement',
+                        'Execution\u00a0agreement', 'Execution\u2002agreement', 'Execution\u3000agreement'):
             with self.subTest(heading=repr(heading)):
                 self.write_intent(heading)
                 with self.assertRaises(ValueError):
--- /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/pm/scripts/agreement_contract.py (before)
+++ /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/pm/scripts/agreement_contract.py (after)
@@ -145,7 +145,7 @@
     exists and it is exactly `## <heading>`, this raises rather than letting a
     near-miss select legacy behavior."""
     masked = mask_fences(text)
-    label = r'[ \t]+'.join(re.escape(word) for word in heading.split())
+    label = r'[^\S\r\n]+'.join(re.escape(word) for word in heading.split())
     attempts = list(re.finditer(r'^ {0,3}#{1,6}[ \t]*' + label
                                 + r'\b[^\n]*$', masked, re.M | re.I))
     if not attempts:
--- /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/tests/test_review_boundary_variants.py (before)
+++ /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/tests/test_review_boundary_variants.py (after)
@@ -40,7 +40,7 @@
         self.assertEqual(json.loads(result.stdout)['status'], 'shipped')
 
     def test_whitespace_inside_agreement_label_fails_closed(self):
-        for spacing in ('  ', '\t', '   ', ' \t '):
+        for spacing in ('  ', '\t', '   ', ' \t ', '\u00a0', '\u2002', '\u3000'):
             with self.subTest(spacing=repr(spacing)):
                 self.setUp()
                 self.legacy_record()
@@ -51,7 +51,7 @@
                 self.assertIn('Execution agreement', result.stdout)
 
     def test_whitespace_inside_requirements_label_fails_closed(self):
-        for spacing in ('  ', '\t'):
+        for spacing in ('  ', '\t', '\u00a0', '\u2002', '\u3000'):
             with self.subTest(spacing=repr(spacing)):
                 self.setUp()
                 self.legacy_record()
```

## Executed targeted commands and results

Working directory: this notes file's directory. Every test, reproduction, and sync invocation used `RINGER_NO_SELF_UPDATE=1 RINGER_NO_CATALOG_REFRESH=1 PYTHONDONTWRITEBYTECODE=1`; the following shell block spells out that common environment once for readability.

```sh
export RINGER_NO_SELF_UPDATE=1 RINGER_NO_CATALOG_REFRESH=1 PYTHONDONTWRITEBYTECODE=1

# Before source fix, after adding the Unicode parameters: exit 1.
python3 -m unittest discover -s /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/tests -p test_review_boundary_variants.py -v > red-boundary.log 2>&1

# After one-line canonical fix: exit 0.
python3 /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/scripts/sync_execution_contract.py --build-swarm /Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm

# Unmodified test execution, avoiding cases whose fixtures write Git: exit 0.
PYTHONPATH=/Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/tests python3 -m unittest test_execution_contract.AgreementSectionCliTests test_execution_contract.ExtraChannelCliTests test_execution_contract.ContractParityTests.test_vendored_copy_is_byte_identical test_pm_evidence_channels test_review_boundary_variants -v > green-cli-contract.log 2>&1

# Remaining narrow loader/parity cases with simulated committed-file reads: exit 0.
python3 verify_no_git.py > green-loader-parity.log 2>&1

# Final explicit byte-parity check: exit 0.
python3 /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/scripts/sync_execution_contract.py --build-swarm /Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm --check > parity.log
```

Sync output:

```text
Imported canonical agreement contract: /Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins/pm/scripts/agreement_contract.py SHA-256 9f41dfc54df2d8971f386a53bd9cb18ebbef4be92e45ef71c19b3d32b0ac7e28
```

[CLI/contract/evidence/boundary output](green-cli-contract.log): **47 tests, OK**, exit 0. This includes all 9 PM boundary tests, all 20 evidence-channel tests, 17 contract CLI tests, and the byte-parity test. Valid canonical sections and distinct scalar evaluator identities still ship; ASCII malformed headings block; ordinary topic titles remain legacy absence.

[Loader/parity output](green-loader-parity.log): **8 tests, OK**, exit 0, comprising the other 5 contract parity tests and the 3 canonical runtime heading tests. Also **20 direct before/after parser cases passed**: six Unicode rejection transitions, eight ASCII/Unicode mid-title genuine absences, and six CR/LF/CRLF exclusions. Direct checks load the saved pre-change contract without modifying live source.

These eight unittest cases retain their assertions and actual parser/loader logic, but their Git fixture boundary is adapted only in this worker's [verify_no_git.py](verify_no_git.py): scratch directories replace fixture repositories; commits become no-ops; `agreement.load` receives simulated `ls-tree` and committed/index `show` bytes. PM validation still uses the actual acceptance CLI. This honors the prohibition on Git writes and is **not a fresh verification of real Git integration**.

The first scratch harness invocation exited 1 before running tests because both test directories contain `test_review_boundary_variants.py` and import-path mutation selected the PM module. Saved output: [harness-import-error.log](harness-import-error.log). Fixed only the scratch harness to import the canonical test file by explicit path, then obtained the 8 passing tests above. No product change was needed.

Final parity output:

```text
PASS: agreement contract byte parity, SHA-256 9f41dfc54df2d8971f386a53bd9cb18ebbef4be92e45ef71c19b3d32b0ac7e28
```

A final Python snapshot diff also asserted that each contract's entire content equals its pre-change bytes with only the separator replacement, and that canonical/PM SHA-256 values match. Full diff above confirms only parameter additions in the two owned tests.

## Limits and handoff

No Git writes (including scratch repositories), installs, publication, GUI, process-command-line inspection, Ringer engine edits, or unrelated source edits. No broad runtime/plugin suites rerun; the lead's earlier 200/149 runs are not claimed as this worker's evidence. The five unrelated parked-residue tests in the canonical boundary file were not rerun; only its three heading tests were relevant. No live Ringer or deployment/evidence-authenticity verification. Eight tests use the explicitly disclosed Git fixture adaptation.

Source/package refresh, generated copies, release documentation typos, and any publication remain with the lead. This worker completed the canonical correction, exact PM source sync, both regression parameter extensions, and targeted verification.
