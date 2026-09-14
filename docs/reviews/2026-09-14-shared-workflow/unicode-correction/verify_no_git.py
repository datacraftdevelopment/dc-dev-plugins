"""Narrow loader/parity checks with committed-file reads simulated; never invokes Git."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

RUNTIME = Path('/Users/joe/Agentic-Mini/_Core/library/skills/agent-operations/build-swarm/scripts')
PLUGIN = Path('/Users/joe/Agentic-Mini/_Core/_Plugins/dc-dev-plugins')
sys.path[:0] = [str(RUNTIME), str(PLUGIN / 'tests')]
import agreement
import test_execution_contract as parity
spec = importlib.util.spec_from_file_location('runtime_boundary', RUNTIME / 'test_review_boundary_variants.py')
runtime_boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime_boundary)


def committed_read(args, cwd, **kwargs):
    """Provide only the three read results agreement.load requests."""
    if args == ['git', 'ls-tree', 'HEAD', '--', 'intent.md']:
        data = b'100644 blob fixture\tintent.md\n'
    elif args in (['git', 'show', 'HEAD:intent.md'], ['git', 'show', ':intent.md']):
        data = (Path(cwd) / 'intent.md').read_bytes()
    else:
        raise AssertionError(('unexpected Git operation', args))
    return subprocess.CompletedProcess(args, 0, stdout=data)


def runtime_load(self, intent):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'intent.md').write_text(intent)
        try:
            result = agreement.load(tmp, 'intent.md')
        except ValueError as exc:
            return subprocess.CompletedProcess([], 1, stdout='', stderr=str(exc))
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(result), stderr='')


loader = unittest.defaultTestLoader
suite = unittest.TestSuite()
for name in loader.getTestCaseNames(parity.ContractParityTests):
    if name != 'test_vendored_copy_is_byte_identical':
        suite.addTest(parity.ContractParityTests(name))
suite.addTests(loader.loadTestsFromTestCase(runtime_boundary.RuntimeHeadingWhitespace))
with patch.object(agreement, 'subprocess', types.SimpleNamespace(run=committed_read)), \
     patch.object(parity.ContractParityTests, 'runtime_load', runtime_load), \
     patch.object(runtime_boundary, 'scratch_repo', lambda: Path(tempfile.mkdtemp())), \
     patch.object(runtime_boundary.rt, 'commit', lambda repo: None):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    sys.exit(1)

# Inspect the actual shared parser before/after independently of the Git seam.
old = types.ModuleType('before_contract')
exec(compile(Path('before/0').read_text(), 'before/0', 'exec'), old.__dict__)
new = agreement.contract
checks = 0
for heading in ('Execution agreement', 'Evidence requirements'):
    for spacing in ('\u00a0', '\u2002', '\u3000'):
        text = '## ' + heading.replace(' ', spacing) + '\n'
        assert old.locate(text, heading) is None
        try:
            new.locate(text, heading)
        except ValueError as exc:
            assert str(exc) == 'expected exactly one ## ' + heading + ' heading'
        else:
            raise AssertionError(('Unicode label accepted', heading, spacing))
        checks += 1
    for spacing in (' ', '\u00a0', '\u2002', '\u3000'):
        text = '## Notes on the ' + heading.replace(' ', spacing) + '\n'
        assert old.locate(text, heading) is None
        assert new.locate(text, heading) is None
        checks += 1
    for spacing in ('\r', '\n', '\r\n'):
        text = '## ' + heading.replace(' ', spacing) + '\n'
        assert old.locate(text, heading) is None
        assert new.locate(text, heading) is None
        checks += 1
print(f'PASS: {checks} direct before/after parser cases (Unicode rejection, topic prefix restriction, CR/LF exclusion)')
