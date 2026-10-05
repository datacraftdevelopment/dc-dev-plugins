import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'pm/scripts/stacks.py'
TABLE = ROOT / 'pm/stacks.json'
VERCEL = ['vercel@claude-plugins-official', 'frontend-design@claude-plugins-official',
          'context7@claude-plugins-official']


class StackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.settings = self.repo / '.claude' / 'settings.json'

    def run_cli(self, *args, ok=True):
        p = subprocess.run(['python3', str(SCRIPT), '--root', str(self.repo), *args],
                           capture_output=True, text=True)
        if ok: self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout) if ok else p

    def write_settings(self, data):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps(data, indent=2) + '\n')

    def test_table_names_every_plugin_with_its_marketplace(self):
        table = json.loads(TABLE.read_text())['stacks']
        self.assertEqual(set(self.run_cli('list')), set(table))
        for name, stack in table.items():
            self.assertTrue(stack['plugins'], name)
            for plugin in stack['plugins']:
                self.assertRegex(plugin, r'^[a-z0-9-]+@[a-z0-9-]+$')

    def test_detect_reads_files_folders_and_extensions(self):
        self.assertEqual(self.run_cli('detect')['detected'], {})
        (self.repo / 'vercel.json').write_text('{}')
        (self.repo / 'supabase').mkdir()
        (self.repo / 'Client.fmp12').write_text('')
        found = self.run_cli('detect')['detected']
        self.assertEqual(found['vercel'], ['vercel.json'])
        self.assertEqual(found['supabase'], ['supabase/'])
        self.assertEqual(found['filemaker'], ['*.fmp12'])

    def test_plan_changes_nothing(self):
        out = self.run_cli('plan', 'vercel')
        self.assertEqual(out['status'], 'planned')
        self.assertEqual(out['add'], VERCEL)
        self.assertFalse(self.settings.exists())

    def test_apply_creates_settings_and_prints_install_commands(self):
        out = self.run_cli('apply', 'vercel')
        self.assertEqual(out['status'], 'applied')
        self.assertEqual(json.loads(self.settings.read_text()),
                         {'enabledPlugins': {p: True for p in VERCEL}})
        self.assertEqual(out['install_commands'],
                         [f'claude plugin install {p} --scope project' for p in VERCEL])

    def test_apply_keeps_what_the_repo_already_decided(self):
        self.write_settings({'permissions': {'deny': ['Bash(rm -rf*)']},
                             'enabledPlugins': {'context7@claude-plugins-official': False,
                                                'other@somewhere': True}})
        out = self.run_cli('apply', 'vercel')
        after = json.loads(self.settings.read_text())
        self.assertEqual(out['kept_disabled'], ['context7@claude-plugins-official'])
        self.assertIs(after['enabledPlugins']['context7@claude-plugins-official'], False)
        self.assertIs(after['enabledPlugins']['other@somewhere'], True)
        self.assertIs(after['enabledPlugins']['vercel@claude-plugins-official'], True)
        self.assertEqual(after['permissions'], {'deny': ['Bash(rm -rf*)']})

    def test_second_apply_leaves_the_file_byte_identical(self):
        self.run_cli('apply', 'vercel', 'supabase')
        before = self.settings.read_bytes()
        out = self.run_cli('apply', 'vercel', 'supabase')
        self.assertEqual(out['status'], 'unchanged')
        self.assertEqual(out['add'], [])
        self.assertEqual(self.settings.read_bytes(), before)

    def test_broken_settings_and_unknown_stack_are_refused_untouched(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{ not json')
        p = self.run_cli('apply', 'vercel', ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(self.settings.read_text(), '{ not json')
        self.settings.unlink()
        p = self.run_cli('apply', 'rails', ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(self.settings.exists())


if __name__ == '__main__':
    unittest.main()
