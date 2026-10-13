"""Runway's modules must parse on Python 3.9: no single-quoted f-string may span lines (PEP 701, 3.12+).
Run: python3 -m pytest -q test_py39_syntax.py."""
import io
import sys
import tokenize
import unittest
from pathlib import Path

RUNWAY = Path(__file__).resolve().parents[1]


def multiline_fstring_lines(src):
    """Lines holding a newline token inside an f-string replacement field (needs the 3.12+ tokenizer)."""
    bad, depth = [], 0
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        name = tokenize.tok_name[tok.type]
        if name == "FSTRING_START":
            depth += 1
        elif name == "FSTRING_END":
            depth -= 1
        elif depth and name in ("NL", "NEWLINE"):
            bad.append(tok.start[0])
    return bad


class Py39Syntax(unittest.TestCase):
    """On 3.12+ the tokenizer shows f-string tokens, so look for a field that spans lines. On an older python3
    the file itself is the test: it must compile there."""

    def test_no_fstring_field_spans_lines(self):
        for path in sorted(RUNWAY.glob("*.py")):
            with self.subTest(file=path.name):
                src = path.read_text()
                if sys.version_info >= (3, 12):
                    self.assertEqual(multiline_fstring_lines(src), [], f"{path.name}: f-string field spans lines")
                else:
                    compile(src, str(path), "exec")

    def test_detector_flags_the_known_bad_shape(self):
        bad = 'x = f"a ({s or \'t \'\n    + str(1)})"\n'
        if sys.version_info >= (3, 12):
            self.assertTrue(multiline_fstring_lines(bad))
        else:
            with self.assertRaises(SyntaxError):
                compile(bad, "bad.py", "exec")


if __name__ == "__main__":
    unittest.main()
