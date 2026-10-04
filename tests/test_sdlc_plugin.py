"""sdlc plugin: the gate-hook kit (installer + gate script) and the review-policy pieces.

Hook cases run the command string the installer writes into .claude/settings.json,
through a shell with the event JSON on stdin, the way the host runs it.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'sdlc'
INSTALLER = PLUGIN / 'scripts/install_gates.py'
KIT_GATE = PLUGIN / 'kit/sdlc_gate.py'
MARKER = '.claude/hooks/sdlc_gate.py'

CONFIG = {
    'version': 1,
    'production': [
        {'name': 'prod-deploy', 'match': r'\bdeploy\b.*--prod\b', 'action': 'deny',
         'reason': 'Production deploys are applied by a human.',
         'approval': 'Ask the release owner to run the deploy.'},
        {'name': 'db-push', 'match': r'\bdb push\b', 'action': 'ask',
         'reason': 'Schema pushes change shared data.',
         'approval': 'The session owner approves in the prompt.'},
    ],
    'protected': [
        {'name': 'generated', 'paths': ['src/gen/**'], 'action': 'deny',
         'reason': 'Generated code is rebuilt, never edited.',
         'approval': 'Change the generator input and regenerate.'},
        {'name': 'migrations', 'paths': ['migrations/'], 'action': 'ask',
         'reason': 'Migrations change shared data.',
         'approval': 'The session owner approves in the prompt.'},
    ],
    'tests': ['tests/**'],
}

FILES = {
    'README.md': 'fixture\n',
    'src/app.py': 'print("app")\n',
    'src/generic.py': 'print("generic")\n',
    'src/gen/client.py': '# generated\n',
    'migrations/001.sql': 'select 1;\n',
    'tests/test_status.py': 'def test_status():\n    assert True\n',
}


def run_installer(repo, *extra):
    return subprocess.run([sys.executable, str(INSTALLER), '--repo', str(repo), *extra],
                          capture_output=True, text=True)


def state_line(result):
    """The installer's plan line about its state folder."""
    (line,) = [text for text in result.stdout.splitlines() if 'create .claude/sdlc/state/' in text]
    return line


class RepoCase(unittest.TestCase):
    """A committed fixture repo in a path with a space."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.unresolved = Path(self.tmp.name) / 'repo with spaces'
        self.unresolved.mkdir()
        self.repo = self.unresolved.resolve()
        self.git('init', '-q')
        self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        for rel, text in FILES.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.commit_all('baseline')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              text=True, capture_output=True)

    def commit_all(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)

    @property
    def settings_path(self):
        return self.repo / '.claude/settings.json'

    @property
    def config_path(self):
        return self.repo / '.claude/sdlc/gates.json'

    @property
    def state_dir(self):
        """Installer backups, and the gate's state when the folder is not a git repo."""
        return self.repo / '.claude/sdlc/state'

    @property
    def gate_state(self):
        """Lock and log: inside the git directory, out of reach of `git clean -x`."""
        return self.repo / '.git/sdlc-gate'


class GateCase(RepoCase):
    """Fixture repo with the kit installed, CONFIG in place and everything committed."""

    def setUp(self):
        super().setUp()
        result = run_installer(self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.config_path.write_text(json.dumps(CONFIG, indent=2) + '\n')
        self.commit_all('install gates')

    def hook_command(self, event='PreToolUse'):
        settings = json.loads(self.settings_path.read_text())
        commands = [h['command'] for group in settings['hooks'][event] for h in group['hooks']
                    if MARKER in h['command']]
        self.assertEqual(len(commands), 1, commands)
        return commands[0]

    def hook(self, payload, env=None):
        if isinstance(payload, dict):
            event = payload.get('hook_event_name', 'PreToolUse')
            payload = json.dumps(payload)
        else:
            event = 'PreToolUse'
        full_env = os.environ.copy()
        full_env['CLAUDE_PROJECT_DIR'] = str(self.repo)
        full_env.update(env or {})
        return subprocess.run(['/bin/bash', '-c', self.hook_command(event)], input=payload,
                              capture_output=True, text=True, env=full_env, cwd=self.repo)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(self.repo / MARKER), *args],
                              capture_output=True, text=True, cwd=self.repo)

    def edit(self, target, tool='Edit', key='file_path', cwd=None):
        path = target if os.path.isabs(str(target)) or cwd else str(self.repo / target)
        return {'hook_event_name': 'PreToolUse', 'tool_name': tool, 'session_id': 's1',
                'cwd': str(cwd or self.repo), 'tool_input': {key: str(path)}}

    def bash(self, command):
        return {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'session_id': 's1',
                'cwd': str(self.repo), 'tool_input': {'command': command}}

    def stop(self, active=False):
        return {'hook_event_name': 'Stop', 'session_id': 's1', 'cwd': str(self.repo),
                'stop_hook_active': active}

    def assertAllowed(self, result):
        self.assertEqual((result.returncode, result.stdout.strip()), (0, ''), result.stderr)

    def assertDenied(self, result, *needles):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stderr)

    def assertAsks(self, result, *needles):
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual(out['hookEventName'], 'PreToolUse')
        self.assertEqual(out['permissionDecision'], 'ask')
        for needle in needles:
            self.assertIn(needle, out['permissionDecisionReason'])

    def log_entries(self):
        path = self.gate_state / 'gate-log.jsonl'
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class ProtectedPathTests(GateCase):
    def test_unprotected_edit_is_allowed(self):
        self.assertAllowed(self.hook(self.edit('src/app.py')))

    def test_deny_rule_blocks_with_reason_and_approval_route(self):
        self.assertDenied(self.hook(self.edit('src/gen/client.py')),
                          'generated', 'Generated code is rebuilt, never edited.',
                          'Change the generator input and regenerate.')

    def test_ask_rule_pauses_for_the_user(self):
        self.assertAsks(self.hook(self.edit('migrations/001.sql')),
                        'migrations', 'Migrations change shared data.',
                        'The session owner approves in the prompt.')

    def test_write_tool_is_gated(self):
        self.assertDenied(self.hook(self.edit('src/gen/new_client.py', tool='Write')))

    def test_notebook_edit_uses_notebook_path(self):
        self.assertDenied(self.hook(self.edit('src/gen/nb.ipynb', tool='NotebookEdit',
                                              key='notebook_path')))

    def test_double_star_spans_directories(self):
        self.assertDenied(self.hook(self.edit('src/gen/deep/er/x.py')))

    def test_prefix_lookalike_is_not_matched(self):
        self.assertAllowed(self.hook(self.edit('src/generic.py')))

    def test_trailing_slash_protects_the_whole_directory(self):
        self.assertAsks(self.hook(self.edit('migrations/sub/002.sql')))

    def test_match_ignores_case(self):
        self.assertDenied(self.hook(self.edit('SRC/GEN/client.py')))

    def test_relative_path_resolves_against_event_cwd(self):
        self.assertDenied(self.hook(self.edit('gen/client.py', cwd=self.repo / 'src')))

    def test_symlinked_spelling_of_the_repo_path_is_matched(self):
        self.assertDenied(self.hook(self.edit(self.unresolved / 'src/gen/client.py')))

    def test_path_outside_the_repo_is_not_gated(self):
        outside = Path(self.tmp.name).resolve() / 'elsewhere/src/gen/client.py'
        self.assertAllowed(self.hook(self.edit(outside)))

    def test_tool_the_kit_does_not_gate_is_allowed(self):
        self.assertAllowed(self.hook(self.edit('src/gen/client.py', tool='Read')))

    def test_rule_applies_inside_a_nested_worktree_of_the_repo(self):
        self.assertDenied(self.hook(self.edit('.claude/worktrees/feature-x/src/gen/client.py')), 'generated')
        self.assertAllowed(self.hook(self.edit('.claude/worktrees/feature-x/src/app.py')))


class ProductionGateTests(GateCase):
    def test_deny_rule_blocks_with_reason_and_approval_route(self):
        self.assertDenied(self.hook(self.bash('npm run deploy -- --prod')),
                          'prod-deploy', 'Production deploys are applied by a human.',
                          'Ask the release owner to run the deploy.')

    def test_ask_rule_pauses_for_the_user(self):
        self.assertAsks(self.hook(self.bash('supabase db push')),
                        'db-push', 'Schema pushes change shared data.')

    def test_unmatched_command_is_allowed(self):
        self.assertAllowed(self.hook(self.bash('npm run build')))

    def test_match_ignores_case_like_a_case_insensitive_filesystem_does(self):
        self.assertDenied(self.hook(self.bash('NPM RUN DEPLOY -- --PROD')), 'prod-deploy')

    def test_command_continued_over_lines_is_still_matched(self):
        self.assertDenied(self.hook(self.bash('npm run deploy \\\n  -- \\\n  --prod')), 'prod-deploy')

    def test_monitor_runs_commands_so_it_is_gated_like_bash(self):
        payload = self.bash('npm run deploy -- --prod')
        payload['tool_name'] = 'Monitor'
        self.assertDenied(self.hook(payload), 'prod-deploy')


class ShellWriteTests(GateCase):
    """A shell command that plainly writes a protected or locked path is refused at the call.

    The check is precision-first. What it cannot read with certainty it lets through, and the
    commit check and the Stop hook catch the change afterwards."""

    def assertDecisions(self, expected):
        for command, want in expected:
            with self.subTest(command=command):
                result = self.hook(self.bash(command))
                if want == 'allow':
                    self.assertAllowed(result)
                elif want == 'deny':
                    self.assertDenied(result)
                else:
                    self.assertAsks(result)

    def test_plain_writes_to_protected_paths_follow_the_rule(self):
        self.assertDecisions([
            ("sed -i '' 's/a/b/' src/gen/client.py", 'deny'),
            ("FOO=1 sed -i '' 's/a/b/' src/gen/client.py", 'deny'),
            ("perl -pi -e 's/a/b/' src/gen/client.py", 'deny'),
            ('echo x > src/gen/new.py', 'deny'),
            ('echo x >> migrations/001.sql', 'ask'),
            ('tee migrations/002.sql < /dev/null', 'ask'),
            ('rm src/gen/client.py', 'deny'),
            ('rm src/gen/*.py', 'deny'),
            ('rm -rf src/gen', 'deny'),
            ('rm -rf src', 'deny'),
            ('mv src/gen/client.py /tmp/moved.py', 'deny'),
            ('mv src/app.py src/gen/', 'deny'),
            ('cp /tmp/other.py src/gen/client.py', 'deny'),
            ('cd src && echo x > gen/client.py', 'deny'),
            ('bash -c "echo x > src/gen/client.py"', 'deny'),
            ('rm "$CLAUDE_PROJECT_DIR/src/gen/client.py"', 'deny'),
        ])

    def test_writes_behind_heredocs_keywords_wrappers_and_redirect_forms_are_refused(self):
        self.assertDecisions([
            ("cat <<'EOF' > src/gen/client.py\n# x\nEOF", 'deny'),
            ('cat <<EOF | tee src/gen/x.py\nhi\nEOF', 'deny'),
            ('cat <<EOF > /tmp/a.txt && rm -rf src/gen\nhi\nEOF', 'deny'),
            ('if [ -f src/gen/client.py ]; then rm src/gen/client.py; fi', 'deny'),
            ('timeout 60 rm -rf src/gen', 'deny'),
            ("env LC_ALL=C sed -i '' 's/a/b/' src/gen/client.py", 'deny'),
            ('nohup bash -c "rm -rf src/gen"', 'deny'),
            ('cp /tmp/c.py src/gen/client.py 2>/dev/null', 'deny'),
            ('cp /tmp/c.py src/gen/client.py 2>&1', 'deny'),
            ('echo x >| src/gen/client.py', 'deny'),
            ('echo x &> src/gen/client.py', 'deny'),
            ('(cd src && ls) && cp /tmp/a.py src/gen/a.py', 'deny'),
            ('echo $(rm src/gen/client.py)', 'deny'),
            ('echo x > .claude/settings.jso?', 'ask'),
        ])

    def test_what_the_check_cannot_read_is_let_through_and_caught_at_commit(self):
        self.assertDecisions([
            ('python3 -c "open(\'src/gen/client.py\', \'w\').write(\'x\')"', 'allow'),
            ("python3 - <<'PY'\nopen('migrations/001.sql', 'a').write('x')\nPY", 'allow'),
            ("bash <<'EOF'\nrm -rf src/gen\nEOF", 'allow'),
            ('black src/gen', 'allow'),
            ("find src/gen -name '*.py' -delete", 'allow'),
            ('git checkout -- migrations/001.sql', 'allow'),
            ('git -C src rm gen/client.py', 'allow'),
            ('echo "an unclosed quote > src/gen/client.py', 'allow'),
        ])
        (self.repo / 'src/gen/client.py').write_text('# changed by a script\n')
        self.assertAsks(self.hook(self.bash('git commit -am "x"')), 'src/gen/client.py')

    def test_reads_mentions_and_neighbouring_writes_are_left_alone(self):
        self.assertDecisions([
            ('cat src/gen/client.py', 'allow'),
            ('grep -rn ping src/gen', 'allow'),
            ("grep -rn '>' src/", 'allow'),
            ('diff src/gen/client.py src/app.py', 'allow'),
            ('cp src/gen/client.py /tmp/copy.py', 'allow'),
            ('git diff migrations/001.sql', 'allow'),
            ('git add src/gen/client.py', 'allow'),
            ('git restore --staged src/gen/client.py', 'allow'),
            ('git reset HEAD src/gen/client.py', 'allow'),
            ('git reset .', 'allow'),
            ('echo "see src/gen/client.py"', 'allow'),
            ('python3 src/app.py src/gen/client.py', 'allow'),
            ('echo x > /tmp/elsewhere.txt', 'allow'),
            ('echo x > src/app.py', 'allow'),
            ('cp /tmp/logo.png .', 'allow'),
            ('mv README.md src/', 'allow'),
            ('git mv README.md src/', 'allow'),
            ('ln -s ../shared .', 'allow'),
            ('rsync -a tpl/ .', 'allow'),
            ("ls migrations/  # what's pending", 'allow'),
            ('rm -rf dist  # rebuilt from src', 'allow'),
            ("find src -name '*.py' -exec cp {} /tmp/backup/ \\;", 'allow'),
            ('cd "$(mktemp -d)" && cp -r ~/tpl/. .', 'allow'),
            ('rm "notes [2024-01].md"', 'allow'),
            ('touch "app/[user-id]/page.tsx"', 'allow'),
        ])

    ORDINARY = [
        ('chmod +x *.sh', 'allow'),
        ('rm -f *.log', 'allow'),
        ("sed -i '' 's/a/b/' *.md", 'allow'),
        ("sed -i '' 's/a/b/' src/*.py", 'allow'),
        ("find . -name '*.py' -exec grep -l TODO {} +", 'allow'),
        ("find src -name '*.py' -exec wc -l {} +", 'allow'),
        ("find . -name '*.pyc' -delete", 'allow'),
        ('rm -rf node_modules build', 'allow'),
        ('git checkout .', 'allow'),
        ('for f in *.md; do echo "$f"; done', 'allow'),
        ('cp /tmp/x.txt .', 'allow'),
        ('mv src/app.py tests/', 'allow'),
        ("# re-run the one that's failing\npython3 -m pytest tests/test_status.py -q", 'allow'),
    ]

    def ordinary_files(self):
        (self.repo / 'run.sh').write_text('#!/bin/sh\n')
        (self.repo / 'debug.log').write_text('x\n')

    def test_ordinary_wildcards_and_finds_are_left_alone(self):
        self.ordinary_files()
        self.assertDecisions(self.ORDINARY)

    def test_ordinary_commands_are_left_alone_under_a_lock(self):
        self.ordinary_files()
        self.assertEqual(self.cli('lock').returncode, 0)
        self.assertDecisions(self.ORDINARY + [
            ('python3 -m pytest tests/test_status.py -q && git commit --allow-empty -m '
             '"$(cat <<\'EOF\'\nFix #12\nEOF\n)"', 'allow'),
        ])

    def test_rule_that_starts_with_a_wildcard_is_matched_by_path_not_by_word(self):
        rule = {'action': 'deny', 'reason': 'Protected.', 'approval': 'Ask the user.'}
        self.config_path.write_text(json.dumps({'version': 1, 'protected': [
            dict(rule, name='anygen', paths=['**/generated/**']), dict(rule, name='sql', paths=['**/*.sql'])]}))
        (self.repo / 'src/generated').mkdir()
        (self.repo / 'src/generated/a.ts').write_text('x\n')
        self.assertDecisions([
            ('rm -rf src/generated', 'deny'),
            ('rm src/generated/a.ts', 'deny'),
            ('echo x > src/generated/b.ts', 'deny'),
            ('echo x > db/seed.sql', 'deny'),
            ("sed -i '' 's/generated/build/' README.md", 'allow'),
            ("sed -i '' 's/v1.sql/v2.sql/' README.md", 'allow'),
            ('python3 -c "import duckdb; print(duckdb.sql(\'select 42\').fetchall())"', 'allow'),
            ('node -e "console.log(\'generated\')"', 'allow'),
            ('rm -rf src/gen', 'allow'),
        ])

    def test_locked_file_cannot_be_rewritten_through_the_shell(self):
        self.assertEqual(self.cli('lock', '--reason', 'fix #12').returncode, 0)
        self.assertDecisions([
            ("sed -i '' 's/True/False/' tests/test_status.py", 'deny'),
            ("echo '# skip' >> tests/test_status.py", 'deny'),
            ("cat <<'EOF' >> tests/test_status.py\n# x\nEOF", 'deny'),
            ('rm tests/test_status.py', 'deny'),
            ('rm -rf tests', 'deny'),
            ('mv tests/test_status.py /tmp/gone.py', 'deny'),
            ('cp /tmp/other.py tests/test_status.py', 'deny'),
        ])
        self.assertIn('test-lock', self.hook(self.bash('rm tests/test_status.py')).stderr)

    def test_locked_file_can_still_be_run_restored_and_joined_by_new_tests(self):
        self.assertEqual(self.cli('lock').returncode, 0)
        self.assertDecisions([
            ('python3 -m pytest tests/test_status.py -q', 'allow'),
            ('pytest tests/test_status.py', 'allow'),
            ('cat tests/test_status.py', 'allow'),
            ('git checkout -- tests/test_status.py', 'allow'),
            ('git restore tests/test_status.py', 'allow'),
            ("echo 'def test_new(): pass' > tests/test_new.py", 'allow'),
        ])

    def test_a_fault_inside_the_shell_check_lets_the_command_through(self):
        # The layer is a convenience with backstops behind it, so its own failure must not block work.
        result = self.hook(self.bash('rm ' + 'a' * 70000))
        self.assertAllowed(result)


class SelfProtectionTests(GateCase):
    def test_editing_gate_files_asks(self):
        for rel in ('.claude/sdlc/gates.json', MARKER, '.claude/settings.json',
                    '.claude/settings.local.json'):
            with self.subTest(rel=rel):
                self.assertAsks(self.hook(self.edit(rel)), 'gate')

    def test_other_hook_scripts_in_the_repo_are_not_gate_files(self):
        self.assertAllowed(self.hook(self.edit('.claude/hooks/format.sh', tool='Write')))
        self.assertAllowed(self.hook(self.bash('chmod +x .claude/hooks/format.sh')))

    def test_editing_user_settings_asks_because_they_can_switch_hooks_off(self):
        home = Path(self.tmp.name).resolve() / 'home'
        payload = self.edit(home / '.claude/settings.json')
        self.assertAsks(self.hook(payload, env={'HOME': str(home)}), 'gate')

    def test_shell_writes_to_gate_files_ask(self):
        for command in ("sed -i '' 's/deny/ask/' .claude/sdlc/gates.json",
                        'rm -rf .claude/hooks',
                        'rm -rf .claude',
                        'git checkout -- .claude/sdlc/gates.json',
                        f'python3 {MARKER} unlock',
                        'echo {} > .claude/settings.local.json'):
            with self.subTest(command=command):
                self.assertAsks(self.hook(self.bash(command)), 'gate')

    def test_read_only_and_staging_commands_on_gate_files_are_allowed(self):
        for command in ('git add .claude/settings.json .claude/sdlc/gates.json',
                        'git diff .claude/sdlc/gates.json',
                        'cat .claude/sdlc/gates.json',
                        'ls -la .claude',
                        f'python3 {MARKER} status',
                        f'python3 "$CLAUDE_PROJECT_DIR/{MARKER}" lock tests/test_status.py'):
            with self.subTest(command=command):
                self.assertAllowed(self.hook(self.bash(command)))

    def test_shell_check_ignores_case_and_is_not_fooled_by_exempt_looking_commands(self):
        for command in ('rm -rf .Claude/sdlc',
                        'git -C $(reboot) status .claude/sdlc/gates.json',
                        'git diff --output=.claude/sdlc/gates.json',
                        f'python3 $(reboot)/{MARKER} status',
                        'rm -rf .git/sdlc-gate'):
            with self.subTest(command=command):
                self.assertAsks(self.hook(self.bash(command)), 'gate')

    def test_editing_lock_state_asks(self):
        self.assertAsks(self.hook(self.edit('.git/sdlc-gate/test-lock.json', tool='Write')), 'gate')

    def test_symlinked_user_settings_ask_by_either_path(self):
        home = Path(self.tmp.name).resolve() / 'home'
        (home / '.claude').mkdir(parents=True)
        (home / 'dotfiles').mkdir()
        real = home / 'dotfiles/claude-settings.json'
        real.write_text('{}')
        (home / '.claude/settings.json').symlink_to(real)
        for target in (home / '.claude/settings.json', real):
            with self.subTest(target=str(target)):
                self.assertAsks(self.hook(self.edit(target), env={'HOME': str(home)}), 'gate')

    def test_exempt_command_with_a_chained_write_still_asks(self):
        self.assertAsks(self.hook(self.bash('cat .claude/sdlc/gates.json && rm .claude/sdlc/gates.json')))


class TestLockTests(GateCase):
    def lock(self, *args):
        result = self.cli('lock', *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_lock_records_a_baseline_for_the_configured_test_paths(self):
        self.lock('--reason', 'fix #12')
        state = json.loads((self.gate_state / 'test-lock.json').read_text())
        self.assertEqual(list(state['baseline']), ['tests/test_status.py'])
        self.assertEqual(state['reason'], 'fix #12')

    def test_locked_file_cannot_be_edited(self):
        self.lock('--reason', 'fix #12')
        self.assertDenied(self.hook(self.edit('tests/test_status.py')),
                          'test-lock', 'fix #12', 'unlock')

    def test_new_test_file_can_still_be_written(self):
        self.lock()
        self.assertAllowed(self.hook(self.edit('tests/test_more.py', tool='Write')))

    def test_explicit_path_locks_only_that_path(self):
        (self.repo / 'tests/test_other.py').write_text('def test_other():\n    assert True\n')
        self.commit_all('second test')
        self.lock('tests/test_status.py')
        self.assertDenied(self.hook(self.edit('tests/test_status.py')))
        self.assertAllowed(self.hook(self.edit('tests/test_other.py')))

    def test_lock_with_nothing_to_lock_fails(self):
        result = self.cli('lock', 'nothing/**')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.gate_state / 'test-lock.json').exists())

    def test_second_lock_is_refused(self):
        self.lock()
        self.assertEqual(self.cli('lock').returncode, 1)

    def test_unlock_releases_the_files(self):
        self.lock()
        self.assertEqual(self.cli('unlock').returncode, 0)
        self.assertAllowed(self.hook(self.edit('tests/test_status.py')))

    def test_stop_passes_while_locked_files_are_untouched(self):
        self.lock()
        self.assertAllowed(self.hook(self.stop()))

    def test_stop_without_a_lock_passes(self):
        self.assertAllowed(self.hook(self.stop()))

    def test_stop_blocks_once_when_a_locked_file_changed(self):
        self.lock()
        (self.repo / 'tests/test_status.py').write_text('def test_status():\n    pass\n')
        result = self.hook(self.stop())
        self.assertDenied(result, 'tests/test_status.py')
        # A hand edit by the user must never be reverted on the hook's say-so.
        self.assertIn('did not change', result.stderr)

    def test_stop_blocks_when_a_locked_file_was_deleted(self):
        self.lock()
        (self.repo / 'tests/test_status.py').unlink()
        self.assertDenied(self.hook(self.stop()), 'tests/test_status.py')

    def test_second_consecutive_stop_warns_instead_of_looping(self):
        self.lock()
        (self.repo / 'tests/test_status.py').write_text('def test_status():\n    pass\n')
        result = self.hook(self.stop(active=True))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('tests/test_status.py', json.loads(result.stdout)['systemMessage'])

    def test_git_clean_does_not_release_the_lock(self):
        self.lock()
        self.git('clean', '-fdx')
        self.assertDenied(self.hook(self.edit('tests/test_status.py')), 'test-lock')

    def test_locked_file_is_frozen_inside_a_nested_worktree_too(self):
        self.lock()
        self.assertDenied(self.hook(self.edit('.claude/worktrees/feature-x/tests/test_status.py')),
                          'test-lock')

    def test_a_separate_worktree_keeps_its_own_lock(self):
        tree = Path(self.tmp.name).resolve() / 'tree'
        self.git('worktree', 'add', '-q', str(tree), '-b', 'side')
        result = subprocess.run([sys.executable, str(tree / MARKER), 'lock'],
                                capture_output=True, text=True, cwd=tree)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.repo / '.git/worktrees/tree/sdlc-gate/test-lock.json').exists())
        self.assertAllowed(self.hook(self.edit('tests/test_status.py')))

    def test_unreadable_lock_state_fails_closed(self):
        self.lock()
        (self.gate_state / 'test-lock.json').write_text('{not json')
        self.assertDenied(self.hook(self.edit('tests/test_status.py')), 'test-lock')


class CommitGateTests(GateCase):
    def test_clean_tree_commit_is_allowed(self):
        self.assertAllowed(self.hook(self.bash('git commit --allow-empty -m "noop"')))

    def test_unprotected_change_commits_freely(self):
        (self.repo / 'src/app.py').write_text('print("changed")\n')
        self.assertAllowed(self.hook(self.bash('git add -A && git commit -m "app"')))

    def test_commit_with_a_changed_protected_path_asks(self):
        (self.repo / 'migrations/001.sql').write_text('select 2;\n')
        self.assertAsks(self.hook(self.bash('git commit -am "migration"')),
                        'migrations/001.sql', 'migrations')

    def test_shell_routed_change_to_a_deny_path_is_caught_at_commit(self):
        (self.repo / 'src/gen/client.py').write_text('# hand edited\n')
        self.assertAsks(self.hook(self.bash('git -C . commit -am "sneak"')),
                        'src/gen/client.py', 'generated')

    def test_new_untracked_file_under_a_protected_path_asks(self):
        (self.repo / 'migrations/002.sql').write_text('select 3;\n')
        self.assertAsks(self.hook(self.bash('git add -A && git commit -m "new migration"')),
                        'migrations/002.sql')

    def test_changed_gate_config_asks_at_commit(self):
        changed = dict(CONFIG, production=[])
        self.config_path.write_text(json.dumps(changed, indent=2) + '\n')
        self.assertAsks(self.hook(self.bash('git commit -am "loosen"')),
                        '.claude/sdlc/gates.json')

    def test_commit_is_blocked_while_the_test_lock_is_violated(self):
        self.assertEqual(self.cli('lock').returncode, 0)
        (self.repo / 'tests/test_status.py').write_text('def test_status():\n    pass\n')
        self.assertDenied(self.hook(self.bash('git commit -am "fix"')),
                          'test-lock', 'tests/test_status.py')

    def test_long_list_of_changed_protected_paths_is_capped(self):
        for n in range(30):
            (self.repo / f'migrations/{n:03}.sql').write_text('select 9;\n')
        result = self.hook(self.bash('git commit -am "many"'))
        self.assertAsks(result, 'more')
        self.assertLess(len(result.stdout), 3000)

    def test_commit_inside_a_nested_worktree_is_inspected(self):
        tree = self.repo / '.claude/worktrees/feature-x'
        self.git('worktree', 'add', '-q', str(tree), '-b', 'feature-x')
        (tree / 'src/gen/client.py').write_text('# hand edited\n')
        payload = self.bash('git commit -am "sneak"')
        payload['cwd'] = str(tree)
        self.assertAsks(self.hook(payload), 'src/gen/client.py', 'generated')

    def test_git_commands_that_do_not_commit_are_not_inspected(self):
        (self.repo / 'migrations/001.sql').write_text('select 2;\n')
        self.assertAllowed(self.hook(self.bash('git status --short')))


class FailClosedTests(GateCase):
    def test_unparseable_config_blocks_gated_tools(self):
        self.config_path.write_text('{not json')
        self.assertDenied(self.hook(self.edit('src/app.py')), 'gates.json')
        self.assertDenied(self.hook(self.bash('npm run build')), 'gates.json')

    def test_missing_config_blocks_gated_tools(self):
        self.config_path.unlink()
        self.assertDenied(self.hook(self.edit('src/app.py')), 'gates.json')

    def test_invalid_rule_blocks_and_check_names_it(self):
        broken = json.loads(json.dumps(CONFIG))
        broken['protected'][0]['action'] = 'warn'
        self.config_path.write_text(json.dumps(broken))
        self.assertDenied(self.hook(self.edit('src/app.py')), 'gates.json')
        check = self.cli('check')
        self.assertEqual(check.returncode, 1)
        self.assertIn('generated', check.stdout + check.stderr)

    def test_check_rejects_unknown_keys_and_bad_patterns(self):
        for mutate in (lambda c: c.update(protect=[]),
                       lambda c: c['production'][0].update(match='(unclosed'),
                       lambda c: c['protected'][0].pop('approval'),
                       lambda c: c.update(version=2)):
            broken = json.loads(json.dumps(CONFIG))
            mutate(broken)
            self.config_path.write_text(json.dumps(broken))
            with self.subTest(config=broken):
                self.assertEqual(self.cli('check').returncode, 1)

    def test_check_accepts_the_fixture_config(self):
        self.assertEqual(self.cli('check').returncode, 0)

    def test_unparseable_event_blocks(self):
        self.assertDenied(self.hook('not json'))

    def test_blank_command_is_harmless_but_a_missing_one_blocks(self):
        self.assertAllowed(self.hook(self.bash('   ')))
        payload = self.bash('ls')
        del payload['tool_input']['command']
        self.assertDenied(self.hook(payload), 'event')

    def test_stop_is_not_trapped_by_a_broken_config(self):
        self.config_path.write_text('{not json')
        self.assertAllowed(self.hook(self.stop()))

    def test_missing_python_blocks_instead_of_silently_disabling(self):
        result = self.hook(self.edit('src/app.py'), env={'PATH': '/nonexistent'})
        self.assertDenied(result, 'python3')

    def stub_python(self, code):
        bin_dir = Path(self.tmp.name).resolve() / 'stubbin'
        bin_dir.mkdir(exist_ok=True)
        stub = bin_dir / 'python3'
        stub.write_text(f'#!/bin/sh\nexit {code}\n')
        stub.chmod(0o755)
        return {'PATH': f'{bin_dir}:/usr/bin:/bin'}

    def test_python_that_fails_before_the_gate_runs_blocks(self):
        self.assertDenied(self.hook(self.edit('src/app.py'), env=self.stub_python(1)), 'runtime')

    def test_stop_is_not_trapped_by_a_broken_runtime(self):
        self.assertNotEqual(self.hook(self.stop(), env=self.stub_python(1)).returncode, 2)
        self.assertNotEqual(self.hook(self.stop(), env={'PATH': '/nonexistent'}).returncode, 2)
        (self.repo / MARKER).unlink()
        self.assertEqual(self.hook(self.stop()).returncode, 0)

    def test_config_may_leave_out_a_section(self):
        self.config_path.write_text(json.dumps({'version': 1, 'protected': CONFIG['protected']}))
        self.assertEqual(self.cli('check').returncode, 0)
        self.assertAllowed(self.hook(self.bash('npm run deploy -- --prod')))
        self.assertDenied(self.hook(self.edit('src/gen/client.py')))

    def test_check_rejects_globs_the_matcher_cannot_honor(self):
        for paths in (['/abs/gen/**'], ['src/{gen,old}/**'], ['src/[ab].py']):
            broken = json.loads(json.dumps(CONFIG))
            broken['protected'][0]['paths'] = paths
            self.config_path.write_text(json.dumps(broken))
            with self.subTest(paths=paths):
                self.assertEqual(self.cli('check').returncode, 1)


class GateLogTests(GateCase):
    def test_deny_and_ask_are_logged_and_allow_is_not(self):
        self.hook(self.edit('src/app.py'))
        self.hook(self.edit('src/gen/client.py'))
        self.hook(self.bash('supabase db push'))
        entries = self.log_entries()
        self.assertEqual([(e['gate'], e['decision'], e['tool']) for e in entries],
                         [('protected:generated', 'deny', 'Edit'),
                          ('production:db-push', 'ask', 'Bash')])
        self.assertTrue(all(e['at'] and e['session'] == 's1' for e in entries))

    def test_credentials_in_a_refused_command_are_not_written_to_the_log(self):
        self.hook(self.bash('supabase db push --db-url postgresql://admin:hunter2@db.example.com/app'))
        self.hook(self.bash('DEPLOY_TOKEN=abc123 npm run deploy -- --prod --password s3cret'))
        text = (self.gate_state / 'gate-log.jsonl').read_text()
        self.assertEqual(len(self.log_entries()), 2)
        for secret in ('hunter2', 'abc123', 's3cret'):
            self.assertNotIn(secret, text)
        self.assertIn('postgresql://admin:***@db.example.com/app', text)

    def test_log_and_lock_state_stay_out_of_git(self):
        self.hook(self.edit('src/gen/client.py'))
        self.assertEqual(self.cli('lock').returncode, 0)
        self.assertEqual(self.git('status', '--porcelain').stdout, '')


class InstallerTests(RepoCase):
    def sdlc_groups(self, event):
        settings = json.loads(self.settings_path.read_text())
        return [g for g in settings['hooks'][event]
                if any(MARKER in h['command'] for h in g['hooks'])]

    def test_installer_names_the_resolved_target_even_on_a_dry_run(self):
        result = subprocess.run([sys.executable, str(INSTALLER), '--repo', '.', '--dry-run'],
                                capture_output=True, text=True, cwd=self.repo)
        self.assertIn(f'target: {self.repo}', result.stdout)

    def test_fresh_install_writes_the_kit(self):
        result = run_installer(self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.repo / MARKER).read_bytes(), KIT_GATE.read_bytes())
        config = json.loads(self.config_path.read_text())
        self.assertEqual((config['version'], config['production'], config['protected']), (1, [], []))
        self.assertTrue(config['tests'])
        (group,) = self.sdlc_groups('PreToolUse')
        self.assertEqual(group['matcher'], 'Bash|Monitor|Edit|Write|NotebookEdit')
        self.assertEqual(len(self.sdlc_groups('Stop')), 1)
        check = subprocess.run([sys.executable, str(self.repo / MARKER), 'check'],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_install_is_idempotent(self):
        run_installer(self.repo)
        first = self.settings_path.read_bytes()
        second = run_installer(self.repo)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.settings_path.read_bytes(), first)
        self.assertEqual(len(self.sdlc_groups('PreToolUse')), 1)
        self.assertEqual(len(self.sdlc_groups('Stop')), 1)
        self.assertFalse(list(self.state_dir.glob('backups/*')))

    def test_existing_settings_are_preserved_and_backed_up(self):
        original = json.dumps({
            'permissions': {'allow': ['Bash(make test)']},
            'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [
                {'type': 'command', 'command': 'echo other'}]}]},
        }, indent=4)
        self.settings_path.parent.mkdir(parents=True)
        self.settings_path.write_text(original)
        self.assertEqual(run_installer(self.repo).returncode, 0)
        settings = json.loads(self.settings_path.read_text())
        self.assertEqual(settings['permissions'], {'allow': ['Bash(make test)']})
        self.assertEqual(settings['hooks']['PreToolUse'][0]['hooks'][0]['command'], 'echo other')
        self.assertEqual(len(self.sdlc_groups('PreToolUse')), 1)
        backups = list(self.state_dir.glob('backups/settings.json.*'))
        self.assertEqual([b.read_text() for b in backups], [original])

    def test_invalid_settings_abort_before_anything_is_written(self):
        self.settings_path.parent.mkdir(parents=True)
        self.settings_path.write_text('{not json')
        result = run_installer(self.repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('settings.json', result.stderr)
        self.assertEqual(self.settings_path.read_text(), '{not json')
        self.assertFalse((self.repo / MARKER).exists())
        self.assertFalse(self.config_path.exists())

    def test_existing_config_is_never_overwritten(self):
        self.config_path.parent.mkdir(parents=True)
        mine = json.dumps(CONFIG)
        self.config_path.write_text(mine)
        self.assertEqual(run_installer(self.repo).returncode, 0)
        self.assertEqual(self.config_path.read_text(), mine)

    def test_older_gate_script_is_replaced_and_backed_up(self):
        run_installer(self.repo)
        (self.repo / MARKER).write_text('# older build\n')
        self.assertEqual(run_installer(self.repo).returncode, 0)
        self.assertEqual((self.repo / MARKER).read_bytes(), KIT_GATE.read_bytes())
        backups = list(self.state_dir.glob('backups/sdlc_gate.py.*'))
        self.assertEqual([b.read_text() for b in backups], ['# older build\n'])

    def test_dry_run_writes_nothing(self):
        result = run_installer(self.repo, '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.repo / '.claude').exists())

    def test_plan_names_the_folder_the_lock_is_really_kept_in(self):
        line = state_line(run_installer(self.repo))
        self.assertIn('the lock and log are kept in .git/sdlc-gate/', line)
        self.assertNotIn('(lock', line)
        lock = subprocess.run([sys.executable, str(self.repo / MARKER), 'lock'],
                              capture_output=True, text=True, cwd=self.repo)
        self.assertEqual(lock.returncode, 0, lock.stdout + lock.stderr)
        self.assertEqual([p.parent for p in self.repo.rglob('test-lock.json')], [self.gate_state])

    def test_plan_in_a_worktree_points_at_its_own_git_directory(self):
        tree = Path(self.tmp.name).resolve() / 'tree'
        self.git('worktree', 'add', '-q', str(tree), '-b', 'side')
        line = state_line(run_installer(tree, '--dry-run'))
        self.assertIn("the lock and log are kept in this checkout's own git directory", line)
        self.assertNotIn('.git/sdlc-gate/', line)

    def test_missing_repo_is_an_error(self):
        result = run_installer(self.repo / 'nope')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('nope', result.stderr)


class NonGitFolderTests(unittest.TestCase):
    def test_state_falls_back_to_the_claude_folder_without_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'plain'
            (root / 'tests').mkdir(parents=True)
            (root / 'tests/test_a.py').write_text('def test_a():\n    assert True\n')
            self.assertEqual(run_installer(root).returncode, 0)
            lock = subprocess.run([sys.executable, str(root / MARKER), 'lock'],
                                  capture_output=True, text=True, cwd=root)
            self.assertEqual(lock.returncode, 0, lock.stdout + lock.stderr)
            self.assertTrue((root / '.claude/sdlc/state/test-lock.json').exists())

    def test_plan_says_the_state_folder_holds_the_lock_without_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'plain'
            root.mkdir()
            line = state_line(run_installer(root, '--dry-run'))
            self.assertIn('(lock, log and backups', line)
            self.assertNotIn('.git/', line)


class PluginShapeTests(unittest.TestCase):
    SHIPPED = ('kit', 'scripts', 'skills', 'agents', 'templates', 'README.md', '.claude-plugin')

    def shipped_files(self):
        for name in self.SHIPPED:
            path = PLUGIN / name
            if path.is_file():
                yield path
            else:
                yield from (p for p in path.rglob('*')
                            if p.is_file() and '__pycache__' not in p.parts and p.name != '.DS_Store')

    def frontmatter(self, path):
        text = path.read_text()
        match = re.match(r'---\n(.*?)\n---\n', text, re.S)
        self.assertIsNotNone(match, f'{path} has no frontmatter')
        fields = dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line)
        return {k.strip(): v.strip() for k, v in fields.items()}, match.group(0)

    def test_manifest_and_marketplace_entry(self):
        manifest = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['name'], 'sdlc')
        self.assertRegex(manifest['version'], r'^\d+\.\d+\.\d+$')
        market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        entries = [p for p in market['plugins'] if p['name'] == 'sdlc']
        self.assertEqual([p['source'] for p in entries], ['./sdlc'])

    def test_skills_have_trigger_only_descriptions(self):
        for name in ('gate-hooks', 'review-policy'):
            fields, raw = self.frontmatter(PLUGIN / 'skills' / name / 'SKILL.md')
            with self.subTest(skill=name):
                self.assertEqual(fields['name'], name)
                self.assertTrue(fields['description'].strip('"').startswith('Use when'))
                self.assertLessEqual(len(raw), 1024)

    def test_reviewer_agent_is_read_only(self):
        fields, _ = self.frontmatter(PLUGIN / 'agents/policy-reviewer.md')
        self.assertEqual(fields['name'], 'policy-reviewer')
        self.assertEqual(fields['tools'], 'Read, Grep, Glob')

    def test_every_plugin_path_a_skill_names_exists(self):
        for doc in list((PLUGIN / 'skills').rglob('*.md')) + [PLUGIN / 'README.md']:
            for rel in re.findall(r'\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)', doc.read_text()):
                with self.subTest(doc=doc.name, path=rel):
                    self.assertTrue((PLUGIN / rel).exists())

    def test_shipped_files_are_portable(self):
        files = list(self.shipped_files())
        self.assertGreaterEqual(len(files), 9)
        for path in files:
            with self.subTest(path=str(path.relative_to(PLUGIN))):
                self.assertFalse(path.is_symlink())
                self.assertNotIn('/Users/', path.read_text())

    def test_review_template_carries_the_policy_sections(self):
        text = (PLUGIN / 'templates/REVIEW.md').read_text()
        for heading in ('## Passes', '## Severity', '## Nit cap', '## Do not report', '## Evidence'):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_managed_settings_example_is_valid_json(self):
        text = (PLUGIN / 'skills/gate-hooks/managed-settings.md').read_text()
        blocks = re.findall(r'```json\n(.*?)```', text, re.S)
        self.assertTrue(blocks)
        for block in blocks:
            json.loads(block)


if __name__ == '__main__':
    unittest.main()
