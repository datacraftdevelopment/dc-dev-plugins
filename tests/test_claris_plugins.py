import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('filemaker-agentic-development', 'adt-standards-default')


class ClarisPluginTests(unittest.TestCase):
    def fixture(self, root):
        cache = root / 'cache/claris'
        installed = {'plugins': {}}
        for name in NAMES:
            for version in ('0.5.0', '0.6.0'):
                package = cache / name / version
                (package / '.claude-plugin').mkdir(parents=True)
                (package / '.claude-plugin/plugin.json').write_text(json.dumps({
                    'name': name, 'version': version, 'description': name,
                    'displayName': name, 'author': {'name': 'Claris'}, 'license': 'Copyright'}))
                (package / '.in_use').mkdir()
                (package / '.in_use/123').write_text('ephemeral')
                if name == NAMES[0]:
                    (package / 'skills/fm-mcp-guide').mkdir(parents=True)
                    (package / 'skills/fm-mcp-guide/SKILL.md').write_text(
                        '---\nname: fm-mcp-guide\ndescription: Use for FileMaker ADT.\n---\nRead .claude/skills/fm-cli/SKILL.md.\n')
                    (package / 'bin').mkdir()
                    (package / 'bin/adt').write_text('#!/bin/sh\necho fixture\n')
                    (package / 'bin/adt').chmod(0o755)
                    (package / '.mcp.json').write_text(json.dumps({'mcpServers': {'adt-mcp': {
                        'command': '${CLAUDE_PLUGIN_ROOT}/bin/adt', 'args': ['mcp'],
                        'env': {'FM_HTTP_BASE_URL': 'http://127.0.0.1:1366'}}}}))
                else:
                    (package / 'standards').mkdir()
                    (package / 'standards/naming.md').write_text('Names from ' + version)
                    (package / '.claude-plugin/META.json').write_text('{"name":"default"}')
            installed['plugins'][name + '@claris'] = [{'scope': 'user', 'version': '0.5.0',
                'installPath': str(cache / name / '0.5.0')}]
        registry = root / 'installed_plugins.json'
        registry.write_text(json.dumps(installed))
        return cache, registry

    def run_builder(self, root, cache, registry):
        return subprocess.run(['python3', str(ROOT / 'scripts/install_claris.py'),
                               '--cache', str(cache), '--registry', str(registry),
                               '--output', str(root / 'output')], capture_output=True, text=True)

    def test_active_versions_not_highest_cache_and_standards_discovery(self):
        with tempfile.TemporaryDirectory(prefix='claris test ') as tmp:
            root = Path(tmp)
            cache, registry = self.fixture(root)
            before = {p: p.read_bytes() for p in cache.rglob('*') if p.is_file()}
            result = self.run_builder(root, cache, registry)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in NAMES:
                package = root / 'output' / name
                manifest = json.loads((package / '.codex-plugin/plugin.json').read_text())
                self.assertTrue(manifest['version'].startswith('0.5.0+codex.'))
                self.assertEqual(manifest['license'], 'Copyright')
                self.assertFalse((package / '.in_use').exists())
            main = root / 'output' / NAMES[0]
            mcp = json.loads((main / '.mcp.json').read_text())['mcpServers']['adt-mcp']
            self.assertEqual(mcp['command'], str((main / 'bin/adt').resolve()))
            self.assertEqual(mcp['args'], ['mcp'])
            self.assertTrue((main / 'bin/adt').stat().st_mode & 0o100)
            skill = (root / 'output' / NAMES[1] / 'skills/adt-standards-default/SKILL.md').read_text()
            self.assertIn('"pack": "default"', skill)
            self.assertIn('advisory', skill)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            # Follow Claude's selected version on the next refresh.
            state = json.loads(registry.read_text())
            entry = state['plugins'][NAMES[0] + '@claris'][0]
            entry.update(version='0.6.0', installPath=str(cache / NAMES[0] / '0.6.0'))
            registry.write_text(json.dumps(state))
            result = self.run_builder(root, cache, registry)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((main / '.codex-plugin/plugin.json').read_text())
            self.assertTrue(manifest['version'].startswith('0.6.0+codex.'))

    def test_missing_registration_fails_without_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache, registry = self.fixture(root)
            registry.write_text('{"plugins":{}}')
            result = self.run_builder(root, cache, registry)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('No active user installation', result.stderr)

    def test_unowned_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache, registry = self.fixture(root)
            target = root / 'output' / NAMES[0]
            target.mkdir(parents=True)
            (target / 'mine.txt').write_text('keep')
            result = self.run_builder(root, cache, registry)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Refusing to replace unowned destination', result.stderr)
            self.assertEqual((target / 'mine.txt').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
