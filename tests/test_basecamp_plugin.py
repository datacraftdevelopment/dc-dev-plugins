from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1] / 'basecamp-dc'
CONFIG = {'project_id': '111', 'todoset_id': '222', 'todolist_id': '333'}


def write_config(root, payload=None):
    path = Path(root) / '.basecamp' / 'config.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload or CONFIG))
    return path


def run_setup(root, plugin=PLUGIN):
    return subprocess.run([sys.executable, str(plugin / 'scripts/bc_setup.py'), '--root', str(root)],
                          capture_output=True, text=True)


def hook_command(plugin=PLUGIN):
    hooks = json.loads((plugin / 'hooks/hooks.json').read_text())
    return hooks['hooks']['SessionStart'][0]['hooks'][0]['command']


def run_hook(event_cwd, plugin=PLUGIN, project_dir=None, shell_cwd=None):
    """Run the SessionStart hook exactly as the host would: the hooks.json command
    string through a shell, the event JSON on stdin."""
    env = os.environ.copy()
    env.pop('CLAUDE_PROJECT_DIR', None)
    if project_dir is not None:
        env['CLAUDE_PROJECT_DIR'] = str(project_dir)
    command = hook_command(plugin).replace('${CLAUDE_PLUGIN_ROOT}', str(plugin))
    return subprocess.run(['bash', '-c', command], input=json.dumps({'cwd': str(event_cwd)}),
                          capture_output=True, text=True, env=env,
                          cwd=str(shell_cwd or tempfile.gettempdir()))


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bc-setup-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dest = self.root / 'docs/agents/client-face.md'

    def test_refuses_without_config(self):
        result = run_setup(self.root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('.basecamp/config.json', result.stderr)
        self.assertFalse(self.dest.exists())

    def test_refuses_invalid_config(self):
        write_config(self.root, payload='{not json')
        result = run_setup(self.root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('config.json', result.stderr)
        self.assertFalse(self.dest.exists())

    def test_installs_template_then_idempotent(self):
        write_config(self.root)
        first = run_setup(self.root)
        self.assertEqual(first.returncode, 0, first.stderr)
        installed = self.dest.read_text()
        self.assertEqual(installed, (PLUGIN / 'templates/client-face.md').read_text())
        second = run_setup(self.root)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.dest.read_text(), installed)

    def test_never_overwrites_hand_edits(self):
        write_config(self.root)
        self.dest.parent.mkdir(parents=True)
        self.dest.write_text('# hand-edited contract\n')
        result = run_setup(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dest.read_text(), '# hand-edited contract\n')

    def test_refuses_symlink_destination(self):
        write_config(self.root)
        self.dest.parent.mkdir(parents=True)
        target = self.root / 'elsewhere.md'
        target.write_text('do not touch\n')
        self.dest.symlink_to(target)
        result = run_setup(self.root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('symlink', result.stderr)
        self.assertTrue(self.dest.is_symlink())
        self.assertEqual(target.read_text(), 'do not touch\n')

    def test_refuses_dangling_symlink_destination(self):
        write_config(self.root)
        self.dest.parent.mkdir(parents=True)
        self.dest.symlink_to(self.root / 'missing.md')
        result = run_setup(self.root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / 'missing.md').exists())

    def test_refuses_symlink_parent_without_writing_outside_repo(self):
        write_config(self.root)
        outside = self.root / 'external-docs'
        outside.mkdir()
        (self.root / 'docs').symlink_to(outside, target_is_directory=True)
        result = run_setup(self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((outside / 'agents/client-face.md').exists())

    def test_directory_is_not_reported_as_an_installed_contract(self):
        write_config(self.root)
        self.dest.mkdir(parents=True)
        result = run_setup(self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.dest.is_dir())



class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bc-hook-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_silent_without_config(self):
        result = run_hook(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_context_from_event_cwd(self):
        write_config(self.root)
        result = run_hook(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('111', result.stdout)
        self.assertIn('client face', result.stdout)

    @unittest.skipUnless(shutil.which('git'), 'git not available')
    def test_finds_git_root_from_nested_cwd(self):
        write_config(self.root)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        nested = self.root / 'src/deep'
        nested.mkdir(parents=True)
        result = run_hook(nested)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('111', result.stdout)

    def test_claude_project_dir_still_wins(self):
        write_config(self.root)
        elsewhere = self.root / 'unrelated'
        elsewhere.mkdir()
        result = run_hook(elsewhere, project_dir=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('111', result.stdout)

    def test_unconfigured_host_project_does_not_fall_through(self):
        write_config(self.root)
        current = self.root / 'unconfigured'
        current.mkdir()
        result = run_hook(self.root, project_dir=current, shell_cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_unconfigured_event_project_does_not_fall_through(self):
        write_config(self.root)
        current = self.root / 'unconfigured'
        current.mkdir()
        result = run_hook(current, shell_cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_spaced_plugin_root(self):
        spaced = self.root / 'plugin root with spaces' / 'basecamp-dc'
        shutil.copytree(PLUGIN, spaced,
                        ignore=shutil.ignore_patterns('.DS_Store', '__pycache__'))
        project = self.root / 'project'
        write_config(project)
        result = run_hook(project, plugin=spaced)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('111', result.stdout)


if __name__ == '__main__':
    unittest.main()
