"""Regression tests at the receipt/verdict command-line boundary; no GUI needed."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1] / "ui-test"
SCRIPTS = PLUGIN / "skills/ui-test/scripts"
REFERENCES = PLUGIN / "skills/ui-test/references"
# A fully encoded 2x2 RGB PNG (red, green, blue, white), not a screenshot.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP4z8DA8J+BkYHh"
    "////DAAe9gT9Ce00PgAAAABJRU5ErkJggg=="
)


class UIEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "runner"
        self.run.mkdir()
        self.other = self.root / "verifier"
        self.other.mkdir()
        self.png = self.run / "evidence/after.png"
        self.png.parent.mkdir()
        self.png.write_bytes(PNG)
        self.truth = {
            "case_id": "current-case", "assertions": {"status": {"expected": "Posted"}},
            "artifacts_required": ["evidence/after.png"], "mutations_allowed": False,
        }
        self.receipt = {
            "case_id": "current-case", "execution_outcome": "PASS-OBSERVED",
            "tool_used": "fixture", "read_method": "pixels",
            "observations": {"status": {"raw_text": "Posted", "source": "pixels", "artifact_ref": "a1"}},
            "artifacts": [{"id": "a1", "path": "evidence/after.png"}],
            "mutations_made": False,
        }
        self.verdict = {
            "case_id": "current-case", "verdict": "PASS",
            "per_assertion": [{"id": "status", "observed_by_verifier": "Posted", "artifact_ref": "a1", "result": "pass"}],
            "basis": "Fixture pixels, independently transcribed",
        }

    def save(self):
        for name, value in (("truth", self.truth), ("receipt", self.receipt), ("verdict", self.verdict)):
            if value is not None:
                (self.run / (name + ".json")).write_text(json.dumps(value))

    def check(self, kind="verdict", cwd=None, no_site=False):
        self.save()
        cmd = [sys.executable] + (["-S"] if no_site else [])
        cmd += [str(SCRIPTS / ("check_" + kind + ".py")), "--truth", str(self.run / "truth.json"), "--receipt", str(self.run / "receipt.json")]
        if kind == "verdict":
            cmd += ["--verdict", str(self.run / "verdict.json")]
        return subprocess.run(cmd, cwd=cwd or self.run, text=True, capture_output=True)

    def rejected(self, kind="verdict", reason=None):
        result = self.check(kind)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        if reason:
            self.assertIn(reason, result.stdout)

    def test_valid_real_png_passes_both_checks(self):
        for kind in ("receipt", "verdict"):
            result = self.check(kind)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("mechanical", result.stdout.lower())

    def test_relative_artifacts_resolve_from_receipt_in_separate_cwd(self):
        for kind in ("receipt", "verdict"):
            result = self.check(kind, cwd=self.other)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_receipt_cannot_pass(self):
        self.receipt = None
        self.rejected(reason="receipt")

    def test_empty_artifacts_cannot_pass(self):
        self.truth["artifacts_required"] = []
        self.receipt["artifacts"] = []
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "artifact")

    def test_missing_png_cannot_pass(self):
        self.png.unlink()
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "artifact")

    def test_directory_in_place_of_png_cannot_pass(self):
        self.png.unlink()
        self.png.mkdir()
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "artifact")

    def test_png_signature_and_padding_are_not_decodable(self):
        self.png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "PNG")

    def test_truncated_png_is_rejected(self):
        self.png.write_bytes(PNG[:50])
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "PNG")

    def test_unknown_verifier_artifact_is_rejected(self):
        self.verdict["per_assertion"][0]["artifact_ref"] = "absent"
        self.rejected(reason="artifact_ref")

    def test_unknown_runner_artifact_is_rejected(self):
        self.receipt["observations"]["status"]["artifact_ref"] = "absent"
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "artifact_ref")

    def test_legacy_path_references_and_flat_observations_remain_valid(self):
        del self.receipt["artifacts"][0]["id"]
        self.receipt["observations"]["status"] = "Posted"
        self.verdict["per_assertion"][0]["artifact_ref"] = "evidence/after.png"
        for kind in ("receipt", "verdict"):
            result = self.check(kind)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_unknown_reference_with_legacy_artifact_without_id_is_rejected(self):
        del self.receipt["artifacts"][0]["id"]
        self.receipt["observations"]["status"] = "Posted"
        self.verdict["per_assertion"][0]["artifact_ref"] = "absent"
        self.rejected(reason="artifact_ref")

    def test_precondition_and_unexpected_references_must_name_artifacts(self):
        for field, ref_key in (("preconditions", "evidence_ref"), ("unexpected", "artifact_ref")):
            self.receipt[field] = [{ref_key: "absent"}]
            for kind in ("receipt", "verdict"):
                with self.subTest(field=field, kind=kind):
                    self.rejected(kind, ref_key)
            del self.receipt[field]

    def test_no_receipt_is_needed_to_report_blocked_verification(self):
        self.receipt = None
        self.verdict = {"case_id": "current-case", "verdict": "BLOCKED", "basis": "runner receipt unavailable"}
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stdout)
        self.assertIn("runner receipt unavailable", result.stdout)
        self.assertNotIn("contract violations", result.stdout)

    def test_non_png_format_is_rejected_even_with_png_filename(self):
        self.png.write_bytes(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"))
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "PNG")

    def test_case_ids_must_be_current_matching_nonempty_strings(self):
        for document in (self.truth, self.receipt, self.verdict):
            for bad in (None, "", " ", 1, "old-case"):
                with self.subTest(document=list(document), bad=bad):
                    document["case_id"] = bad
                    self.rejected(reason="case_id")
            document["case_id"] = "current-case"

    def test_receipt_check_requires_nonempty_truth_case_id(self):
        self.truth["case_id"] = None
        self.rejected("receipt", "case_id")

    def test_literal_whitespace_is_not_stripped(self):
        self.receipt["observations"]["status"]["raw_text"] = " Posted\n"
        self.rejected("receipt", "status")
        self.receipt["observations"]["status"]["raw_text"] = "Posted"
        self.verdict["per_assertion"][0]["observed_by_verifier"] = " Posted\n"
        self.rejected(reason="status")

    def test_matching_literal_whitespace_is_preserved(self):
        self.truth["assertions"]["status"]["expected"] = " Posted\n"
        self.receipt["observations"]["status"]["raw_text"] = " Posted\n"
        self.verdict["per_assertion"][0]["observed_by_verifier"] = " Posted\n"
        for kind in ("receipt", "verdict"):
            result = self.check(kind)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_duplicate_verdict_assertion_ids_are_rejected(self):
        self.verdict["per_assertion"].append(dict(self.verdict["per_assertion"][0]))
        self.rejected(reason="duplicate")

    def test_duplicate_artifact_ids_are_rejected(self):
        self.receipt["artifacts"].append(dict(self.receipt["artifacts"][0]))
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "duplicate")

    def test_duplicate_json_assertion_keys_are_rejected(self):
        self.save()
        (self.run / "truth.json").write_text('{"case_id":"current-case","assertions":{"status":"wrong","status":"Posted"}}')
        self.truth = None
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "duplicate")

    def test_empty_assertions_cannot_pass(self):
        self.truth["assertions"] = {}
        self.verdict["per_assertion"] = []
        for kind in ("receipt", "verdict"):
            self.rejected(kind, "assertions")

    def test_verifier_validates_runner_values_and_mutation_contract(self):
        self.receipt["observations"]["status"]["raw_text"] = "Draft"
        self.rejected(reason="status")
        self.receipt["observations"]["status"]["raw_text"] = "Posted"
        self.receipt["mutations_made"] = True
        self.rejected(reason="mutations")

    def test_negative_outcomes_without_evidence_are_not_malformed(self):
        for outcome in ("BLOCKED", "FAIL"):
            self.receipt = {"case_id": "current-case", "execution_outcome": outcome,
                            "blocker": {"reason": "window unavailable"}, "notes": "window unavailable"}
            self.verdict = {"case_id": "current-case", "verdict": outcome, "basis": "window unavailable"}
            for kind in ("receipt", "verdict"):
                with self.subTest(outcome=outcome, kind=kind):
                    result = self.check(kind)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(outcome, result.stdout)
                    self.assertIn("window unavailable", result.stdout)
                    self.assertNotIn("contract violations", result.stdout)

    def test_runner_negative_outcome_cannot_become_product_pass(self):
        for outcome in ("BLOCKED", "FAIL"):
            self.receipt["execution_outcome"] = outcome
            self.rejected(reason=outcome)

    def test_missing_pillow_has_actionable_error(self):
        for kind in ("receipt", "verdict"):
            result = self.check(kind, no_site=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Pillow", result.stdout)
            self.assertIn("requirements.txt", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_templates_harvest_required_pngs_and_resolve_runtime_paths(self):
        schema = (REFERENCES / "receipt-schema.md").read_text()
        truth = json.loads(schema.split("```json\n", 1)[1].split("```", 1)[0])
        template = json.loads((REFERENCES / "manifest-template.json").read_text())
        expected = template["tasks"][0]["expect_files"]
        for path in truth["artifacts_required"]:
            self.assertIn(path.replace("invoice-post", "<case_id>"), expected)
        for task in template["tasks"]:
            self.assertNotIn("CLAUDE_PLUGIN_ROOT", task["check"])
            self.assertIn("<ui-test-plugin-root>", task["check"])
        example = json.loads((REFERENCES / "example-probe/manifest.json").read_text())
        example_truth = json.loads((REFERENCES / "example-probe/truth.json").read_text())
        for path in example_truth["artifacts_required"]:
            self.assertIn(path, example["tasks"][0]["expect_files"])


if __name__ == "__main__":
    unittest.main()
