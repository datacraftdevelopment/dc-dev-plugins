"""Codex install without the plugin-creator helper scripts (gone in Codex 0.159)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_codex  # noqa: E402


def package(root, folder, **manifest):
    p = root / 'plugins' / folder
    (p / '.codex-plugin').mkdir(parents=True)
    (p / 'skills').mkdir()
    data = {'name': folder, 'version': '1.0.0+codex.abc', 'skills': './skills/', **manifest}
    (p / '.codex-plugin/plugin.json').write_text(json.dumps(data))
    return p


class CodexInstallTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.market = self.root / '.agents/plugins/marketplace.json'

    def test_existing_entries_keep_their_metadata_and_order(self):
        self.market.parent.mkdir(parents=True)
        before = {'name': 'personal', 'interface': {'displayName': 'Mine'}, 'plugins': [
            {'name': 'other', 'source': {'source': 'local', 'path': './plugins/other'}},
            {'name': 'pm', 'source': {'source': 'local', 'path': './plugins/pm'},
             'policy': {'installation': 'AVAILABLE'}, 'category': 'Productivity'}]}
        self.market.write_text(json.dumps(before))
        pm = package(self.root, 'pm')
        with patch.object(build_codex, 'run') as run:
            build_codex.install([pm], self.market)
        self.assertEqual(json.loads(self.market.read_text()), before)
        run.assert_called_once_with('codex', 'plugin', 'add', 'pm@personal')

    def test_new_package_is_added_to_the_marketplace(self):
        pm = package(self.root, 'pm')
        with patch.object(build_codex, 'run') as run:
            build_codex.install([pm], self.market)
        data = json.loads(self.market.read_text())
        self.assertEqual(data['name'], 'personal')
        self.assertEqual(data['plugins'], [{'name': 'pm', 'source': {'source': 'local', 'path': './plugins/pm'}}])
        run.assert_called_once_with('codex', 'plugin', 'add', 'pm@personal')

    def test_entry_pointing_elsewhere_is_refused_before_any_install(self):
        self.market.parent.mkdir(parents=True)
        self.market.write_text(json.dumps({'name': 'personal', 'plugins': [
            {'name': 'pm', 'source': {'source': 'local', 'path': './elsewhere/pm'}}]}))
        pm = package(self.root, 'pm')
        with patch.object(build_codex, 'run') as run, self.assertRaisesRegex(ValueError, 'another source'):
            build_codex.install([pm], self.market)
        run.assert_not_called()

    def test_bad_manifest_stops_before_the_marketplace_changes(self):
        pm = package(self.root, 'pm', name='not-pm')
        with patch.object(build_codex, 'run') as run, self.assertRaisesRegex(ValueError, 'manifest name'):
            build_codex.install([pm], self.market)
        self.assertFalse(self.market.exists())
        run.assert_not_called()

    def test_missing_skills_folder_is_refused(self):
        pm = package(self.root, 'pm')
        (pm / 'skills').rmdir()
        with self.assertRaisesRegex(ValueError, 'skills'):
            build_codex.validate_package(pm)

    def test_invalid_catalog_is_left_byte_for_byte_and_nothing_installs(self):
        pm = package(self.root, 'pm')
        self.market.parent.mkdir(parents=True)
        for catalog in ('{"plugins": []}', '{"name": "", "plugins": []}', '{"name": "  ", "plugins": []}',
                        '{"name": 42, "plugins": []}', '{"name": "personal", "plugins": {}}',
                        '{"name": "personal", "plugins": ["pm"]}', '[]'):
            with self.subTest(catalog=catalog):
                self.market.write_text(catalog)
                with patch.object(build_codex, 'run') as run, self.assertRaises(ValueError):
                    build_codex.install([pm], self.market)
                self.assertEqual(self.market.read_text(), catalog)
                run.assert_not_called()

    def test_malformed_packages_are_refused(self):
        def skill(p, text):
            (p / 'skills/one').mkdir()
            (p / 'skills/one/SKILL.md').write_text(text)
        cases = {
            'no frontmatter': lambda p: skill(p, '# just a heading\n'),
            'unclosed frontmatter': lambda p: skill(p, '---\nname: one\n'),
            'bad yaml': lambda p: skill(p, '---\nname: [one\n---\n'),
            'no description': lambda p: skill(p, '---\nname: one\n---\nbody\n'),
            'blank name': lambda p: skill(p, '---\nname: ""\ndescription: d\n---\n'),
            'folder without SKILL.md': lambda p: (p / 'skills/one').mkdir(),
        }
        for label, breaks in cases.items():
            with self.subTest(label):
                pm = package(Path(tempfile.mkdtemp()), 'pm')
                breaks(pm)
                with self.assertRaisesRegex(ValueError, 'frontmatter'):
                    build_codex.validate_package(pm)
        pm = package(Path(tempfile.mkdtemp()), 'pm', mcpServers='./.mcp.json')
        with self.assertRaisesRegex(ValueError, 'missing'):
            build_codex.validate_package(pm)
        for text in ('not json', '[]', '{"mcpServers": []}'):
            with self.subTest(mcp=text):
                (pm / '.mcp.json').write_text(text)
                with self.assertRaisesRegex(ValueError, 'MCP'):
                    build_codex.validate_package(pm)
        pm = package(Path(tempfile.mkdtemp()), 'pm', interface={'composerIcon': './assets/icon.png'})
        with self.assertRaisesRegex(ValueError, 'composerIcon'):
            build_codex.validate_package(pm)

    def test_a_good_package_passes(self):
        pm = package(self.root, 'pm', mcpServers='./.mcp.json')
        (pm / '.mcp.json').write_text('{"mcpServers": {}}')
        (pm / 'skills/one').mkdir()
        (pm / 'skills/one/SKILL.md').write_text('---\nname: one\ndescription: >\n  Folded text.\n---\nbody\n')
        build_codex.validate_package(pm)


if __name__ == '__main__':
    unittest.main()
