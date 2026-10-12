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
        with self.assertRaisesRegex(ValueError, 'skills folder'):
            build_codex.validate_package(pm)


if __name__ == '__main__':
    unittest.main()
