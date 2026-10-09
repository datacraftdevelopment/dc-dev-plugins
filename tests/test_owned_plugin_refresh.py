import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_codex
import refresh_codex


class OwnedPluginRefreshTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'source'
        source.mkdir()
        subprocess.run(['git', 'init', '-q', str(source)], check=True)
        plugin = source / 'pm'
        (plugin / '.claude-plugin').mkdir(parents=True)
        (plugin / '.claude-plugin/plugin.json').write_text(json.dumps({
            'name': 'pm', 'version': '0.17.0', 'description': 'Fixture'}))
        skill = plugin / 'skills/example/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: example\ndescription: Fixture\n---\nOriginal\n')
        (source / 'scripts').mkdir()
        (source / 'scripts/build_codex.py').write_text('adapter-v1\n')
        subprocess.run(['git', '-C', str(source), 'add', 'pm', 'scripts/build_codex.py'], check=True)
        output = root / 'output'
        output.mkdir()
        return source, output, skill

    def test_new_plugins_are_in_default_catalog(self):
        self.assertTrue({'pm', 'basecamp-dc'} <= set(build_codex.PLUGINS))
        self.assertFalse({'ui-test', 'sdlc'} & set(build_codex.PLUGINS))
        market = json.loads((build_codex.ROOT / '.claude-plugin/marketplace.json').read_text())
        # Only local ./subfolder sources can be packaged; git-subdir pointers
        # (fm-lens, agenticdev-filemaker-standards) live in another repo.
        local = {p['name'] for p in market['plugins'] if isinstance(p['source'], str)}
        # Every local plugin is either packaged for Codex or declared Claude-only.
        self.assertEqual(set(build_codex.PLUGINS) | build_codex.CLAUDE_ONLY, local)
        self.assertFalse(set(build_codex.PLUGINS) & build_codex.CLAUDE_ONLY)

    def test_owned_sources_detect_content_version_and_adapter_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output, skill = self.fixture(Path(tmp))
            with patch.object(build_codex, 'ROOT', source):
                package = build_codex.build_one('pm', output)
                version = json.loads((package / '.codex-plugin/plugin.json').read_text())['version']
                item = {'name': 'pm', 'version': version,
                        'source': {'source': 'local', 'path': str(package)}}
                def issues():
                    return refresh_codex.installed_source_issues(item, source, None, None, {})
                self.assertEqual(issues(), [])
                # Untracked local files must neither ship nor make a build stale.
                (source / 'pm/private-note.txt').write_text('not packaged')
                self.assertEqual(issues(), [])
                original = skill.read_text()
                skill.write_text(original + 'Changed without a version bump\n')
                self.assertTrue(any('source changed' in x for x in issues()), issues())
                skill.write_text(original)
                manifest = source / 'pm/.claude-plugin/plugin.json'
                prior = manifest.read_text()
                data = json.loads(prior)
                data['version'] = '0.18.0'
                manifest.write_text(json.dumps(data))
                self.assertTrue(any('source changed' in x for x in issues()), issues())
                manifest.write_text(prior)
                (source / 'scripts/build_codex.py').write_text('adapter-v2\n')
                self.assertTrue(any('source changed' in x for x in issues()), issues())

    def test_old_marker_requires_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output, _ = self.fixture(Path(tmp))
            with patch.object(build_codex, 'ROOT', source):
                package = build_codex.build_one('pm', output)
                version = json.loads((package / '.codex-plugin/plugin.json').read_text())['version']
                (package / build_codex.MARKER).write_text('{"generator":"legacy"}')
                item = {'name': 'pm', 'version': version,
                        'source': {'source': 'local', 'path': str(package)}}
                self.assertTrue(refresh_codex.installed_source_issues(item, source, None, None, {}))

    def test_promote_replaces_owned_new_plugins_and_preserves_unowned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'output'
            output.mkdir()
            for name in ('pm', 'basecamp-dc'):
                package = root / 'staging' / name
                package.mkdir(parents=True)
                (package / build_codex.MARKER).write_text('{}')
                (package / 'value').write_text('new')
                old = output / name
                old.mkdir()
                (old / build_codex.MARKER).write_text('{}')
                (old / 'value').write_text('old')
                with patch('refresh_codex.subprocess.run'):
                    refresh_codex.promote([package], output, root / 'creator')
                self.assertEqual((old / 'value').read_text(), 'new')
                (old / build_codex.MARKER).unlink()
                with self.assertRaisesRegex(ValueError, 'unowned'):
                    refresh_codex.promote([package], output, root / 'creator')
                self.assertEqual((old / 'value').read_text(), 'new')


if __name__ == '__main__':
    unittest.main()
