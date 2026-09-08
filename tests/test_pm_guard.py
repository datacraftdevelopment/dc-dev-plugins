import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'pm/hooks/credential-guard.sh'


class CredentialGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.outer = Path(self.tmp.name)
        self.repo = self.outer / 'repo with spaces'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'credentials.json').write_text('dummy baseline')
        (self.repo / 'README.md').write_text('safe')
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        (self.repo / 'credentials.json').write_text('dummy changed')
        (self.repo / '.env').write_text('DUMMY=fixture')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              text=True, capture_output=True)

    def guard(self, command, cwd=None, payload_cwd=None):
        payload = {'tool_input': {'command': command}}
        if payload_cwd:
            payload['cwd'] = str(payload_cwd)
        return subprocess.run(['bash', str(HOOK)], cwd=cwd or self.repo,
                              input=json.dumps(payload), capture_output=True, text=True)

    def test_cd_from_outside_repo(self):
        self.assertEqual(self.guard(f'cd "{self.repo}" && git add .env', self.outer).returncode, 2)

    def test_payload_cwd_and_relative_git_c(self):
        self.assertEqual(self.guard('git add .env', self.outer, self.repo).returncode, 2)
        self.assertEqual(self.guard('git -C "repo with spaces" -C . add .env', self.outer).returncode, 2)

    def test_commit_paths_not_index(self):
        self.assertEqual(self.guard('git commit -m fixture -- credentials.json').returncode, 2)
        self.git('add', '.env')
        (self.repo / 'README.md').write_text('changed')
        self.assertEqual(self.guard('git commit -m fixture -- README.md').returncode, 0)
        self.assertEqual(self.guard('git commit --include README.md -m fixture').returncode, 2)

    def test_deletion_can_be_committed(self):
        self.git('rm', '-f', '--cached', 'credentials.json')
        self.assertEqual(self.guard('git commit -m "remove credential"').returncode, 0)

    def test_force_ignored_directory(self):
        (self.repo / '.gitignore').write_text('.env\n')
        self.git('checkout', '--', 'credentials.json')
        self.assertEqual(self.guard('git add -f .').returncode, 2)

    def test_scoped_cd_does_not_leak(self):
        sub = self.repo / 'clean'
        sub.mkdir()
        (sub / 'notes.md').write_text('safe')
        self.assertEqual(self.guard('(cd clean && git add notes.md); git add .env').returncode, 2)

    def test_message_expansion_is_not_a_path(self):
        self.assertEqual(self.guard('git commit -m "$MSG"').returncode, 0)
        self.assertEqual(self.guard('git commit -m "built $(date)"').returncode, 0)
        self.assertEqual(self.guard('git commit -m "built $(git add .env)"').returncode, 2)
        # Unquoted expansion can introduce extra operands after the message.
        self.assertEqual(self.guard('git commit -m $MSG').returncode, 2)

    def test_dynamic_target_and_inspection_failure_block(self):
        self.assertEqual(self.guard('git -C "$TARGET" add .').returncode, 2)
        self.assertEqual(self.guard('git -C /nonexistent-pm-fixture add .env').returncode, 2)

    def test_known_nonrepo_and_unrelated_commands_allowed(self):
        self.assertEqual(self.guard('git add .env', self.outer).returncode, 0)
        self.assertEqual(self.guard('echo "$UNKNOWN"').returncode, 0)

    def test_filename_newline_and_secret_directory(self):
        (self.repo / 'secrets').mkdir()
        (self.repo / 'secrets' / 'line\nbreak').write_text('dummy')
        self.assertEqual(self.guard('git add secrets').returncode, 2)

    def test_null_pathspec_file_cannot_bypass(self):
        (self.repo / 'paths.txt').write_text('.env\n')
        self.assertEqual(self.guard('git add --pathspec-from-file=paths.txt').returncode, 2)

    def test_repo_wide_commands_from_subdirectory(self):
        sub = self.repo / 'clean'
        sub.mkdir()
        self.assertEqual(self.guard('git add -A', sub).returncode, 2)
        self.assertEqual(self.guard('git commit -am fixture', sub).returncode, 2)
        self.git('add', '.env')
        self.assertEqual(self.guard('git commit -m fixture', sub).returncode, 2)

    def test_unchanged_historical_secret_not_newly_staged(self):
        self.git('checkout', '--', 'credentials.json')
        (self.repo / '.env').unlink()
        (self.repo / 'README.md').write_text('safe change')
        self.assertEqual(self.guard('git add .').returncode, 0)

    def test_wrappers_and_dynamic_commands_do_not_bypass(self):
        for command in ('env -i git add .env', 'timeout 5 git add .env',
                        'echo .env | xargs git add', 'g=git; $g add .env', '$g add .env'):
            with self.subTest(command=command):
                self.assertEqual(self.guard(command).returncode, 2)
        self.assertEqual(self.guard('echo git add .env').returncode, 0)

    def test_pipeline_cwd_pushd_and_internal_marker_do_not_bypass(self):
        (self.repo / 'clean').mkdir()
        (self.repo / '__CG_SUB_0__').write_text('safe')
        for command in ('cd clean | cat; git add .env', 'git add __CG_SUB_0__ .env'):
            self.assertEqual(self.guard(command).returncode, 2)
        self.assertEqual(self.guard(f'pushd "{self.repo}" && git add .env', self.outer).returncode, 2)

    def test_shell_line_continuations(self):
        self.assertEqual(self.guard('git \\\nadd .env').returncode, 2)

    def test_git_alias_does_not_bypass(self):
        self.git('config', 'alias.a', 'add')
        self.assertEqual(self.guard('git a .env').returncode, 2)

    def test_missing_python_blocks_relevant_calls(self):
        p = subprocess.run(['/bin/bash', str(HOOK)], cwd=self.repo,
                           env={**os.environ, 'PATH': str(self.outer / 'missing')},
                           input=json.dumps({'tool_input': {'command': 'git add .env'}}),
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 2, p.stderr)

    def test_opaque_heredoc_does_not_get_parsed_as_shell(self):
        command = "python3 - <<'PY'\nprint('git add .env')\nPY\n"
        self.assertEqual(self.guard(command).returncode, 0)
        self.assertEqual(self.guard(command + 'git add .env').returncode, 2)

    def test_candidate_changing_prefix_requires_separate_call(self):
        self.git('checkout', '--', 'credentials.json')
        (self.repo / '.env').unlink()
        self.assertEqual(self.guard('touch .env; git add -A').returncode, 2)
        self.assertEqual(self.guard('echo dummy > .env; git add -A').returncode, 2)


if __name__ == '__main__':
    unittest.main()
