from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'pm'
SP = ROOT / 'pm-sp'

MATT = {'domain-modeling', 'codebase-design', 'research', 'pr'}
OWN = {
    'whats-next', 'stepping-away', 'checkpoint', 'second-opinion',
    'ship-acceptance', 'credential-guard', 'gate-hooks', 'review-policy', 'ui-test',
    'granola-transcript', 'okf', 'design-handoff',
}
# Moved to the agent-runway plugin at 0.3.0, which pm-sp now requires.
RUNWAY = {'grill', 'prototype', 'map', 'spec', 'file-tickets', 'hands-on', 'runway', 'take-back', 'setup',
          'writing-plans', 'subagent-driven-development', 'executing-plans', 'test-driven-development',
          'systematic-debugging', 'verification-before-completion'}
MOVED = {'brainstorming', 'wayfinder', 'grilling', 'using-git-worktrees', 'finishing-a-development-branch',
         'requesting-code-review', 'receiving-code-review', 'dispatching-parallel-agents', 'nested-sessions'}
DROPPED = {'discovery', 'fast-grill', 'orchestrate', 'session-succession',
           'verify-before-done', 'board', 'runway', 'subsessions', 'using-superpowers',
           'to-spec', 'to-tickets', 'implement', 'implement-spec', 'triage'}


def frontmatter_name(path):
    match = re.search(r'^name:\s*(\S+)\s*$', path.read_text(), re.M)
    return match[1] if match else None


class PmSpPluginTests(unittest.TestCase):
    def test_manifest_and_marketplace_entry(self):
        manifest = json.loads((SP / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['name'], 'pm-sp')
        market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        entry = next(p for p in market['plugins'] if p['name'] == 'pm-sp')
        self.assertEqual(entry['source'], './pm-sp')

    def test_skill_set(self):
        skills = {p.parent.name for p in (SP / 'skills').glob('*/SKILL.md')}
        self.assertEqual(skills, MATT | OWN)
        for path in (SP / 'skills').glob('*/SKILL.md'):
            self.assertEqual(frontmatter_name(path), path.parent.name, path)

    def test_skills_survive_compaction(self):
        # Claude Code re-attaches a skill cut at 20,000 characters after compaction.
        for path in (SP / 'skills').glob('*/SKILL.md'):
            self.assertLess(len(path.read_bytes()), 20000, path)

    def test_cross_references_resolve(self):
        skills = MATT | OWN | {p.stem for p in (SP / 'agents').glob('*.md')}
        for path in [*(SP / 'skills').rglob('*'), SP / 'WORKFLOW.md', SP / 'README.md', SP / 'template/CLAUDE.md',
                     *(SP / 'template').rglob('*.md'), *(SP / 'commands').glob('*.md'),
                     *(SP / 'templates').glob('*.md')]:
            if not path.is_file() or path.suffix not in {'.md', '.sh', ''}:
                continue
            text = path.read_text(errors='ignore')
            self.assertNotIn('superpowers:', text.replace('pm-sp:', ''), path)
            self.assertNotIn('setup-matt-pocock-skills', text, path)
            self.assertNotIn('mattpocock-skills:', text, path)
            # A bare pm: reference names the sibling plugin, which a pm-sp machine doesn't have.
            self.assertNotRegex(text, r'(?<![\w-])pm:[a-z]', path)
            for name in re.findall(r'pm-sp:([a-z-]+)', text):
                if name == 'scaffold':
                    continue
                self.assertIn(name, skills, f'{path}: pm-sp:{name}')
            for name in re.findall(r'agent-runway:([a-z-]+)', text):
                self.assertIn(name, RUNWAY, f'{path}: agent-runway:{name}')

    def test_no_dropped_skill_is_relied_on(self):
        allowed = {SP / 'WORKFLOW.md', SP / 'README.md', SP / 'VENDOR.md', SP / 'skills/second-opinion/SKILL.md'}
        for path in SP.rglob('*.md'):
            if path in allowed:
                continue
            text = path.read_text()
            for name in DROPPED | MOVED:
                self.assertNotRegex(text, rf'`{name}`|\({re.escape("../" + name)}/|pm-sp:{name}\b', f'{path}: {name}')
        self.assertFalse((SP / 'template/docs/intent').exists())

    def test_requires_agent_runway(self):
        manifest = json.loads((SP / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['version'], '0.3.0')
        self.assertIn('Requires the agent-runway plugin', manifest['description'])
        self.assertIn('requires agent-runway', (SP / 'README.md').read_text())
        whats_next = (SP / 'skills/whats-next/SKILL.md').read_text()
        self.assertIn('`runway status` and `runway hands-on`', whats_next)
        self.assertNotIn('only when the agent-runway plugin is installed', whats_next)
        self.assertFalse((SP / 'LICENSE.superpowers').exists())

    def test_no_session_start_takeover(self):
        hooks = json.loads((SP / 'hooks/hooks.json').read_text())['hooks']
        self.assertEqual(set(hooks), {'PreToolUse'})

    def test_credential_guard_matches_pm(self):
        for rel in ['hooks/credential-guard.sh', 'hooks/hooks.json', 'scripts/credential_guard.py',
                    'scripts/credential_policy.py', 'scripts/credential-policy.json']:
            self.assertEqual((SP / rel).read_bytes(), (PM / rel).read_bytes(), rel)

    def test_shared_scripts_match_pm(self):
        for rel in ['scripts/session.py', 'scripts/acceptance.py', 'scripts/agreement_contract.py',
                    'scripts/install_gates.py', 'scripts/stacks.py', 'kit/sdlc_gate.py']:
            self.assertEqual((SP / rel).read_bytes(), (PM / rel).read_bytes(), rel)

    def test_credential_guard_suite(self):
        result = subprocess.run(['bash', str(SP / 'hooks/test-credential-guard.sh')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])

    def test_design_doc_acceptance_reads(self):
        sys.path.insert(0, str(SP / 'scripts'))
        try:
            import acceptance
        finally:
            sys.path.pop(0)
        design = ('# Upload design\n\n## Goals\n\nFast.\n\n## Acceptance\n\n'
                  '- [ ] A1: uploading a 20 MB file finishes and the row appears\n'
                  '- [ ] A2: a failed upload says why\n\n## Approaches\n\nOne.\n')
        self.assertEqual(acceptance.intent_criteria(design), {
            'A1': 'uploading a 20 MB file finishes and the row appears',
            'A2': 'a failed upload says why'})

    def test_session_open_and_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = str(SP / 'scripts/session.py')
            opened = subprocess.run([sys.executable, script, '--root', tmp, 'open', '--name', 'joe',
                                     '--intent', 'Plan the import.'], capture_output=True, text=True)
            self.assertEqual(opened.returncode, 0, opened.stderr)
            bound = json.loads(opened.stdout)
            entry = Path(tmp) / 'entry.md'
            entry.write_text('## Shipped\n\n- nothing\n')
            closed = subprocess.run([sys.executable, script, '--root', tmp, 'close', '--session', bound['path'],
                                     '--id', bound['id'], '--entry-file', str(entry)], capture_output=True, text=True)
            self.assertEqual(closed.returncode, 0, closed.stderr)
            self.assertIn('Closed:', (Path(tmp) / bound['path']).read_text())

    def test_session_opens_fuzzy_and_reaim_sets_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = str(SP / 'scripts/session.py')
            opened = subprocess.run([sys.executable, script, '--root', tmp, 'open', '--name', 'joe'],
                                    capture_output=True, text=True)
            self.assertEqual(opened.returncode, 0, opened.stderr)
            bound = json.loads(opened.stdout)
            record = Path(tmp) / bound['path']
            self.assertIn('## Intent\n\n_Not set at the open', record.read_text())
            aimed = subprocess.run([sys.executable, script, '--root', tmp, 'reaim', '--session', bound['path'],
                                    '--id', bound['id'], '--entry', 'Plan the import.'], capture_output=True, text=True)
            self.assertEqual(aimed.returncode, 0, aimed.stderr)
            self.assertIn('Plan the import.', record.read_text())

    def test_vendored_license_and_provenance(self):
        vendor = (SP / 'VENDOR.md').read_text()
        for name in MATT:
            self.assertIn(f'`{name}`', vendor)
        self.assertIn('MIT License', (SP / 'LICENSE.mattpocock').read_text())
        self.assertIn('5beb35b', vendor)

    def test_models_are_pinned(self):
        # Joe's Fable allowance was once spent by subagents inheriting the session's model.
        # Every place that dispatches a subagent or session names the model it expects.
        expected = {
            'skills/codebase-design/DESIGN-IT-TWICE.md': ['`model: opus`'],
            'skills/research/SKILL.md': ['`model: sonnet`'],
            'skills/second-opinion/SKILL.md': ['`claude-opus-5`', '`gpt-5.6-sol`'],
            'WORKFLOW.md': ['`sonnet`', '`opus`', 'Fable and Haiku never run as a subagent'],
        }
        for rel, needles in expected.items():
            text = (SP / rel).read_text()
            for needle in needles:
                self.assertIn(needle, text, rel)
        # No skill hands out the model nobody should spend below the main session.
        for path in (SP / 'skills').rglob('*.md'):
            self.assertNotRegex(path.read_text(), r'model: (fable|haiku)|--model (fable|haiku)', path)

    def test_session_closes_from_a_worktree(self):
        # The session binds an absolute root, so close works after the plan moves into a worktree.
        with tempfile.TemporaryDirectory() as tmp:
            root, elsewhere = Path(tmp) / 'repo', Path(tmp) / 'repo-worktree'
            root.mkdir(); elsewhere.mkdir()
            script = str(SP / 'scripts/session.py')
            opened = subprocess.run([sys.executable, script, '--root', str(root), 'open', '--name', 'joe',
                                     '--intent', 'Build it.'], capture_output=True, text=True)
            bound = json.loads(opened.stdout)
            entry = elsewhere / 'entry.md'
            entry.write_text('## Shipped\n\n- the thing\n')
            closed = subprocess.run([sys.executable, script, '--root', str(root), 'close', '--session', bound['path'],
                                     '--id', bound['id'], '--entry-file', str(entry)],
                                    capture_output=True, text=True, cwd=elsewhere)
            self.assertEqual(closed.returncode, 0, closed.stderr)
            self.assertIn('Closed:', (root / bound['path']).read_text())
        for rel in ['skills/stepping-away/SKILL.md', 'skills/checkpoint/SKILL.md']:
            self.assertIn('--root "<bound-root>"', (SP / rel).read_text(), rel)
        self.assertIn('ROOT="$(git rev-parse --show-toplevel)"', (SP / 'skills/whats-next/SKILL.md').read_text())

    def test_maps_live_in_docs_maps(self):
        # One record: maps live in docs/maps/, never a .scratch/ folder.
        for path in SP.rglob('*.md'):
            self.assertNotIn('.scratch', path.read_text(), path)
        self.assertIn('docs/maps/<effort>/map.md', (SP / 'template/docs/agents/issue-tracker.md').read_text())


if __name__ == '__main__':
    unittest.main()
