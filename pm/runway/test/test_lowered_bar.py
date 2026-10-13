"""Offline tests: the lowered-bar diff scan (gh-91). Real git repos, no model.
Run: python3 -m pytest -q test_lowered_bar.py

Marker strings are built by concatenation so this file does not trip the scan it tests."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lowered_bar  # noqa: E402

NOQA = "# no" + "qa"
TYPE_IGN = "# type: " + "ignore"
NOCOV = "# pragma: " + "no cover"
TSIGN = "// @ts-" + "ignore"
ESL = "// eslint-" + "disable-next-line"
SWL = "// swiftlint:" + "disable all"
SKIPMARK = "@pytest.mark." + "skip"
NOTIMPL = "raise Not" + "ImplementedError"

GOOD_TESTS = ("def test_a():\n    assert f() == 1\n\n\ndef test_b():\n    assert f() == 2\n")
CODE = "def f():\n    x = 1\n    y = 2\n    return x + y\n"


class Repo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")

    def git(self, *a):
        return subprocess.run(["git", *a], cwd=self.repo, text=True, capture_output=True, check=True).stdout

    def write(self, path, text):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def base(self, files):
        for p, t in files.items():
            self.write(p, t)
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("checkout", "-qb", "work")

    def work(self, files, remove=()):
        for p, t in files.items():
            self.write(p, t)
        for p in remove:
            (self.repo / p).unlink()
        self.git("add", "-A")
        self.git("commit", "-qm", "work")

    def scan(self, **kw):
        return lowered_bar.scan(self.repo, "main", "work", **kw)

    def rules(self, **kw):
        return sorted(f["rule"] for f in self.scan(**kw))


class Fires(Repo):
    def test_deleted_test_file(self):
        self.base({"tests/test_x.py": GOOD_TESTS, "x.py": CODE})
        self.work({}, remove=["tests/test_x.py"])
        (f,) = self.scan()
        self.assertEqual((f["rule"], f["file"]), ("deleted-test-file", "tests/test_x.py"))

    def test_removed_python_test_function(self):
        self.base({"tests/test_x.py": GOOD_TESTS})
        self.work({"tests/test_x.py": "def test_a():\n    assert f() == 1\n"})
        (f,) = self.scan()
        self.assertEqual((f["rule"], f["file"]), ("removed-test", "tests/test_x.py"))
        self.assertEqual(f["line"], 5)
        self.assertIn("-def test_b", f["hunk"])

    def test_removed_pytest_class(self):
        self.base({"tests/test_x.py": "class TestA:\n    def test_one(self):\n        assert 1\n\n\ndef test_z():\n    assert 1\n"})
        self.work({"tests/test_x.py": "def test_z():\n    assert 1\n"})
        self.assertEqual(set(self.rules()), {"removed-test"})

    def test_removed_swift_test(self):
        self.base({"Tests/AppTests.swift": "final class AppTests: XCTestCase {\n    func testA() {}\n    func testB() {}\n}\n"})
        self.work({"Tests/AppTests.swift": "final class AppTests: XCTestCase {\n    func testA() {}\n}\n"})
        (f,) = self.scan()
        self.assertEqual(f["rule"], "removed-test")

    def test_skip_markers(self):
        for i, mark in enumerate([SKIPMARK, SKIPMARK + "if(True, reason='x')", "@pytest.mark." + "xfail",
                                  "    pytest." + "skip('no')", "@unittest." + "skip('x')", "    throw XCT" + "Skip()"]):
            with self.subTest(mark=mark):
                self.setUp()
                self.base({"tests/test_x.py": GOOD_TESTS})
                self.work({"tests/test_x.py": f"{mark}\n" + GOOD_TESTS})
                self.assertIn("test-skipped", self.rules())
                self._tmp.cleanup()

    def test_test_file_renamed_out_of_collection(self):
        self.base({"tests/test_x.py": GOOD_TESTS})
        self.work({"tests/disabled_x.py": GOOD_TESTS}, remove=["tests/test_x.py"])
        (f,) = self.scan()
        self.assertEqual((f["rule"], f["file"]), ("test-disabled", "tests/disabled_x.py"))
        self.assertIn("tests/test_x.py", f["hunk"])

    def test_renamed_so_runner_skips_it(self):
        self.base({"tests/test_x.py": GOOD_TESTS})
        self.work({"tests/test_x.py": GOOD_TESTS.replace("def test_b", "def disabled_b")})
        (f,) = self.scan()
        self.assertEqual(f["rule"], "test-disabled")
        self.assertIn("disabled_b", f["why"])

    def test_suppressions(self):
        for mark, path in [(NOQA, "a.py"), (TYPE_IGN, "a.py"), (NOCOV, "a.py"), (TSIGN, "a.ts"),
                           (ESL, "a.js"), (SWL, "a.swift")]:
            with self.subTest(mark=mark):
                self.setUp()
                self.base({path: "x = 1\n"})
                self.work({path: f"x = 1  {mark}\n" if path.endswith("py") else f"{mark}\nx = 1\n"})
                self.assertEqual(self.rules(), ["new-suppression"])
                self._tmp.cleanup()

    def test_assert_replaced_by_pass(self):
        self.base({"tests/test_x.py": GOOD_TESTS})
        self.work({"tests/test_x.py": GOOD_TESTS.replace("assert f() == 2", "pass")})
        (f,) = self.scan()
        self.assertEqual(f["rule"], "weakened-assertion")

    def test_coverage_threshold_lowered(self):
        self.base({"quality.toml": "[coverage]\nfail_under = 90\n"})
        self.work({"quality.toml": "[coverage]\nfail_under = 60\n"})
        self.assertIn("lowered-threshold", self.rules())

    def test_timeout_raised_is_weaker(self):
        self.base({"ci.json": '{"timeout": 30}\n'})
        self.work({"ci.json": '{"timeout": 300}\n'})
        self.assertEqual(self.rules(), ["lowered-threshold"])

    def test_stub_markers(self):
        self.base({"x.py": CODE})
        self.work({"x.py": f"def f():\n    {NOTIMPL}\n"})
        self.assertEqual(self.rules(), ["stub"])

    def test_todo_implement(self):
        self.base({"x.py": "x = 1\n"})
        self.work({"x.py": "x = 1\n# TODO: implement the retry\n"})
        self.assertEqual(self.rules(), ["stub"])

    def test_empty_body_replacing_real_code(self):
        self.base({"x.py": CODE})
        self.work({"x.py": "def f():\n    pass\n"})
        self.assertEqual(self.rules(), ["stub"])

    def test_check_script_edit(self):
        self.base({"check.sh": "pytest\n", "x.py": CODE})
        self.work({"check.sh": "true\n"})
        (f,) = self.scan(check_cmd="bash ./check.sh")
        self.assertEqual((f["rule"], f["file"]), ("check-edited", "check.sh"))

    def test_test_config_and_ci_edit(self):
        self.base({"pytest.ini": "[pytest]\n", "conftest.py": "x = 1\n", ".github/workflows/ci.yml": "a: 1\n"})
        self.work({"pytest.ini": "[pytest]\naddopts = -x\n", "conftest.py": "x = 2\n", ".github/workflows/ci.yml": "a: 2\n"})
        self.assertEqual(self.rules(), ["check-edited"] * 3)

    def test_pyproject_test_section_only(self):
        self.base({"pyproject.toml": "[project]\nname = 'a'\n\n[tool.pytest.ini_options]\naddopts = ''\n"})
        self.work({"pyproject.toml": "[project]\nname = 'b'\n\n[tool.pytest.ini_options]\naddopts = ''\n"})
        self.assertEqual(self.rules(), [])
        self.work({"pyproject.toml": "[project]\nname = 'b'\n\n[tool.pytest.ini_options]\naddopts = '-k nothing'\n"})
        self.assertEqual(self.rules(), ["check-edited"])


class Clean(Repo):
    def test_renamed_test_that_still_runs(self):
        self.base({"tests/test_x.py": GOOD_TESTS})
        self.work({"tests/test_x.py": GOOD_TESTS.replace("def test_b", "def test_b_renamed")})
        self.assertEqual(self.scan(), [])

    def test_moved_test_file_keeps_its_tests(self):
        self.base({"tests/test_x.py": GOOD_TESTS})
        self.git("mv", "tests/test_x.py", "tests/test_y.py")
        self.git("commit", "-qm", "mv")
        self.assertEqual(self.scan(), [])

    def test_test_added_beside_removed_duplicate(self):
        self.base({"tests/test_x.py": GOOD_TESTS + "\n\ndef test_dup():\n    assert f() == 1\n"})
        self.work({"tests/test_x.py": GOOD_TESTS + "\n\ndef test_merged():\n    assert f() == 1\n    assert f() != 0\n"})
        self.assertEqual(self.scan(), [])

    def test_added_tests_and_code(self):
        self.base({"tests/test_x.py": GOOD_TESTS, "x.py": CODE})
        self.work({"tests/test_x.py": GOOD_TESTS + "\n\ndef test_c():\n    assert f() == 3\n",
                   "x.py": CODE + "\n\ndef g():\n    return 2\n"})
        self.assertEqual(self.scan(), [])

    def test_suppression_removed(self):
        self.base({"a.py": f"x = 1  {NOQA}\ny = 2  {TYPE_IGN}\n"})
        self.work({"a.py": "x = 1\ny = 2\n"})
        self.assertEqual(self.scan(), [])

    def test_import_position_noqa_is_not_a_suppression(self):
        self.base({"a.py": "x = 1\n"})
        self.work({"a.py": "x = 1\nimport os  " + NOQA + ": E402\n"})
        self.assertEqual(self.scan(), [])
        self.work({"a.py": "x = 1\nimport os  " + NOQA + ": F401\n"})
        self.assertEqual(self.rules(), ["new-suppression"])

    def test_existing_suppression_kept_on_edited_line(self):
        self.base({"a.py": f"x = 1  {NOQA}\n"})
        self.work({"a.py": f"x = 2  {NOQA}\n"})
        self.assertEqual(self.scan(), [])

    def test_threshold_raised_and_timeout_lowered(self):
        self.base({"quality.toml": "[coverage]\nfail_under = 60\ntimeout = 300\n"})
        self.work({"quality.toml": "[coverage]\nfail_under = 90\ntimeout = 30\n"})
        self.assertEqual(self.scan(), [])

    def test_docs_mentioning_markers_are_ignored(self):
        self.base({"README.md": "hi\n"})
        self.work({"README.md": f"Use `{NOQA}` and `{SKIPMARK}` sparingly. {NOTIMPL}\n"})
        self.assertEqual(self.scan(), [])

    def test_tests_removed_in_a_non_test_file_is_not_a_test_removal(self):
        self.base({"x.py": CODE + "\n\ndef helper():\n    return 1\n"})
        self.work({"x.py": CODE})
        self.assertEqual(self.scan(), [])


class Allowlist(Repo):
    def test_allow_glob_skips_matching_paths(self):
        self.base({"fixtures/t/test_old.py": GOOD_TESTS, "tests/test_x.py": GOOD_TESTS})
        self.work({}, remove=["fixtures/t/test_old.py"])
        self.assertEqual(self.rules(), ["deleted-test-file"])
        self.assertEqual(self.rules(allow=["fixtures/*"]), [])


class CannotRun(Repo):
    def test_bad_ref_is_a_blocking_finding_not_a_pass(self):
        self.base({"x.py": CODE})
        (f,) = lowered_bar.scan(self.repo, "main", "no-such-ref")
        self.assertEqual(f["rule"], "scan-error")

    def test_not_a_repo(self):
        with tempfile.TemporaryDirectory() as d:
            (f,) = lowered_bar.scan(d, "main", "HEAD")
            self.assertEqual(f["rule"], "scan-error")

    def test_scanner_exception_is_a_finding(self):
        self.base({"x.py": CODE})
        self.work({"x.py": CODE + "y = 1\n"})
        orig = lowered_bar.scan_files
        lowered_bar.scan_files = lambda *a, **k: 1 / 0
        self.addCleanup(setattr, lowered_bar, "scan_files", orig)
        (f,) = self.scan()
        self.assertEqual(f["rule"], "scan-error")

    def test_scan_error_cannot_be_cleared(self):
        f = {"rule": "scan-error", "file": "", "line": 0, "hunk": "x"}
        inv = [{"ticket": "#1", "id": "c1", "criterion": "remove the obsolete test"}]
        blocking, cleared = lowered_bar.apply_clearances(
            [f], [{"id": lowered_bar.finding_id(f), "ticket": "#1", "criterion": "c1", "quote": "remove the obsolete test"}], inv)
        self.assertEqual((len(blocking), cleared), (1, []))


class Clearance(unittest.TestCase):
    HIT = {"rule": "deleted-test-file", "file": "tests/test_old.py", "line": 1, "hunk": "x"}
    CRITERION = "Remove the obsolete test for the legacy importer."
    INVENTORY = [{"ticket": "#7", "id": "c1", "criterion": CRITERION},
                 {"ticket": "#8", "id": "c2", "criterion": "The importer reads both formats."}]

    def clear(self, **c):
        return lowered_bar.apply_clearances([self.HIT], [{"id": lowered_bar.finding_id(self.HIT), **c}], self.INVENTORY)

    def test_quote_from_the_named_criterion_clears(self):
        blocking, cleared = self.clear(ticket="#7", criterion="c1", quote=self.CRITERION)
        self.assertEqual((blocking, len(cleared)), ([], 1))
        self.assertIn("#7 criterion c1", cleared[0])

    def test_invented_quote_does_not(self):
        blocking, cleared = self.clear(ticket="#7", criterion="c1", quote="the worker said this was fine")
        self.assertEqual((len(blocking), cleared), (1, []))

    def test_quote_must_come_from_the_named_criterion(self):
        # a real criterion's words, credited to another ticket's criterion, clear nothing
        blocking, cleared = self.clear(ticket="#8", criterion="c2", quote=self.CRITERION)
        self.assertEqual((len(blocking), cleared), (1, []))

    def test_quote_without_a_criterion_id_does_not_clear(self):
        blocking, cleared = self.clear(quote=self.CRITERION)
        self.assertEqual((len(blocking), cleared), (1, []))

    def test_background_text_is_not_a_criterion(self):
        # text that is in the ticket body but not in its parsed acceptance criteria never clears
        blocking, cleared = self.clear(ticket="#7", criterion="background", quote="Background: the importer")
        self.assertEqual((len(blocking), cleared), (1, []))

    def test_no_clearance_blocks(self):
        blocking, _ = lowered_bar.apply_clearances([self.HIT], None, self.INVENTORY)
        self.assertEqual(len(blocking), 1)


if __name__ == "__main__":
    unittest.main()
