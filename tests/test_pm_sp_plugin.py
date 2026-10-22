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

VENDORED = {
    'brainstorming', 'writing-plans', 'subagent-driven-development', 'executing-plans',
    'finishing-a-development-branch', 'using-git-worktrees', 'requesting-code-review',
    'receiving-code-review', 'test-driven-development', 'systematic-debugging',
    'verification-before-completion', 'dispatching-parallel-agents',
}
OWN = {
    'whats-next', 'stepping-away', 'checkpoint', 'nested-sessions', 'second-opinion',
    'ship-acceptance', 'credential-guard', 'gate-hooks', 'review-policy', 'ui-test',
    'granola-transcript', 'okf',
}
DROPPED = {'discovery', 'fast-grill', 'orchestrate', 'session-succession',
           'verify-before-done', 'board', 'runway', 'subsessions', 'using-superpowers'}


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
        self.assertEqual(skills, VENDORED | OWN)
        for path in (SP / 'skills').glob('*/SKILL.md'):
            self.assertEqual(frontmatter_name(path), path.parent.name, path)

    def test_skills_survive_compaction(self):
        # Claude Code re-attaches a skill cut at 20,000 characters after compaction.
        for path in (SP / 'skills').glob('*/SKILL.md'):
            self.assertLess(len(path.read_bytes()), 20000, path)

    def test_cross_references_resolve(self):
        skills = VENDORED | OWN
        for path in [*(SP / 'skills').rglob('*'), SP / 'WORKFLOW.md', SP / 'template/CLAUDE.md']:
            if not path.is_file() or path.suffix not in {'.md', '.sh', ''}:
                continue
            text = path.read_text(errors='ignore')
            self.assertNotIn('superpowers:', text.replace('pm-sp:', ''), path)
            for name in re.findall(r'pm-sp:([a-z-]+)', text):
                if name == 'scaffold':
                    continue
                self.assertIn(name, skills, f'{path}: pm-sp:{name}')

    def test_no_dropped_skill_is_relied_on(self):
        allowed = {SP / 'WORKFLOW.md', SP / 'README.md', SP / 'VENDOR.md',
                   SP / 'skills/second-opinion/SKILL.md', SP / 'skills/nested-sessions/SKILL.md'}
        for path in SP.rglob('*.md'):
            if path in allowed:
                continue
            text = path.read_text()
            for name in DROPPED:
                self.assertNotRegex(text, rf'`{name}`|\({re.escape("../" + name)}/', f'{path}: {name}')
        self.assertFalse((SP / 'template/docs/intent').exists())

    def test_no_session_start_takeover(self):
        hooks = json.loads((SP / 'hooks/hooks.json').read_text())['hooks']
        self.assertEqual(set(hooks), {'PreToolUse'})
        brainstorming = (SP / 'skills/brainstorming/SKILL.md').read_text()
        self.assertNotIn('You MUST use this before any creative work', brainstorming)
        self.assertIn('stop and ask whether to plan it now', brainstorming)
        self.assertIn('## Acceptance', brainstorming)

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

    def test_vendored_license_and_provenance(self):
        self.assertIn('MIT License', (SP / 'LICENSE.superpowers').read_text())
        vendor = (SP / 'VENDOR.md').read_text()
        self.assertIn('2ce8aa1', vendor)
        for name in VENDORED:
            self.assertIn(f'`{name}`', vendor)


if __name__ == '__main__':
    unittest.main()
