from pathlib import Path
import json
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from install_workflow import managed_text, build, sources, connect_agents, REQUIRED_MATT


class WorkflowTests(unittest.TestCase):
    def test_refresh_cli_loads(self):
        script = Path(__file__).resolve().parents[1] / "scripts/refresh_codex.py"
        result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--install", result.stdout)
        self.assertIn("--check", result.stdout)

    def fixture(self, root):
        library = root / 'library'
        for name in ['CLAUDE.md', 'index.md', 'skills/index.md', 'skills/agent-operations/build-swarm/scripts/loop.py']:
            p = library / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('canonical\n')
        for name, category in [('library', 'wiki-engine'), ('build-swarm', 'agent-operations')]:
            p = library / 'skills' / category / name / 'SKILL.md'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f'---\nname: {name}\ndescription: Test skill\n---\nCanonical content\n')
        matt = root / 'matt/1.2.2'
        skills = []
        for name in sorted(REQUIRED_MATT):
            relative = f'skills/engineering/{name}'
            p = matt / relative / 'SKILL.md'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f'---\nname: {name}\ndescription: Test {name}\n---\nRead ./reference.md\n')
            (p.parent / 'reference.md').write_text('resource remains at source\n')
            skills.append(relative)
        (matt / '.claude-plugin').mkdir()
        (matt / '.claude-plugin/plugin.json').write_text(json.dumps({'name':'mattpocock-skills','version':'1.2.2','skills':skills}))
        registry=root/'installed.json'
        registry.write_text(json.dumps({'plugins':{'mattpocock-skills@mattpocock':[{'scope':'user','version':'1.2.2','installPath':str(matt)}]}}))
        return library, registry, matt

    def test_active_source_links_preserve_canonical_files_and_resources(self):
        with tempfile.TemporaryDirectory(prefix='workflow space ') as t:
            root=Path(t);library,registry,matt=self.fixture(root)
            original={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            output=build(library,registry,root/'out')
            for name in REQUIRED_MATT:
                text=(output/'skills'/name/'SKILL.md').read_text()
                self.assertIn(str(matt/'skills/engineering'/name/'SKILL.md'),text)
                self.assertIn('ringer',text)
            self.assertIn('Fable',(output/'skills/grilling/SKILL.md').read_text())
            self.assertIn('wave 1',(output/'skills/build-swarm/SKILL.md').read_text())
            self.assertEqual(original,{p:Path(p).read_bytes() for p in original})
            self.assertFalse(any(p.is_symlink() for p in output.rglob('*')))
            (matt/'skills/engineering/tdd/SKILL.md').write_text('live source edit')
            self.assertIn(str(matt/'skills/engineering/tdd/SKILL.md'),(output/'skills/tdd/SKILL.md').read_text())

    def test_missing_active_or_mismatched_version_fails(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);library,registry,matt=self.fixture(root)
            d=json.loads(registry.read_text());d['plugins']['mattpocock-skills@mattpocock'][0]['version']='9.0.0';registry.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'mismatch'):sources(library,registry)
            registry.write_text('{"plugins":{}}')
            with self.assertRaisesRegex(ValueError,'one active'):sources(library,registry)

    def test_managed_routing_is_idempotent_and_preserves_personal_text(self):
        original='# My preferences\nKeep my notes.\n'
        once=managed_text(original,'first');twice=managed_text(once,'second')
        self.assertTrue(twice.startswith(original))
        self.assertEqual(twice.count('dc-codex-setup:start'),1)
        self.assertEqual(managed_text(twice,'second'),twice)
        with self.assertRaises(ValueError):managed_text('<!-- dc-codex-setup:start -->','new')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);library,registry,matt=self.fixture(root)
            home=root/'codex';home.mkdir();(home/'AGENTS.md').write_text(original)
            connect_agents(library,home)
            before=(home/'AGENTS.md').read_bytes();connect_agents(library,home)
            self.assertEqual(before,(home/'AGENTS.md').read_bytes())
            self.assertEqual((home/'AGENTS.md.before-dc-setup').read_text(),original)
            self.assertEqual((library/'CLAUDE.md').read_text(),'canonical\n')

    def test_unowned_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);library,registry,matt=self.fixture(root)
            dest=root/'out/dc-workflow';dest.mkdir(parents=True);(dest/'mine').write_text('keep')
            with self.assertRaisesRegex(ValueError,'unowned'):build(library,registry,root/'out')
            self.assertEqual((dest/'mine').read_text(),'keep')


class ConnectionRegressionTests(unittest.TestCase):
    def test_malformed_frontmatter_names_the_source(self):
        from install_workflow import metadata
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'SKILL.md'
            for text in ['body only', '\ufeff---\nname: x\n---\n', '---\njust a string\n---\n']:
                p.write_text(text)
                with self.assertRaisesRegex(ValueError,'SKILL.md'):metadata(p)

    def test_stale_source_version_and_missing_links_are_reported(self):
        from refresh_codex import installed_source_issues
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'dc-workflow';(package/'.codex-plugin').mkdir(parents=True)
            (package/'.codex-plugin/plugin.json').write_text('{"version":"0.1.0"}')
            old=root/'old/SKILL.md';new=root/'new/SKILL.md';new.parent.mkdir();new.write_text('new source')
            (package/'.dc-workflow-build.json').write_text(json.dumps({'library':str(root),'mattVersion':'1','sources':{'tdd':str(old)}}))
            item={'name':'dc-workflow','version':'0.1.0','source':{'source':'local','path':str(package)}}
            issues=installed_source_issues(item,root,{'version':'2'},{'tdd':new},{})
            self.assertTrue(any('changed since' in x for x in issues))
            self.assertTrue(any('missing linked' in x for x in issues))

    def test_inventory_failure_does_not_skip_remaining_diagnostics(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout
        import io
        from refresh_codex import connection_report
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);library,registry,matt=WorkflowTests().fixture(root)
            def run(argv,**kwargs):
                if argv[0]=='codex':raise FileNotFoundError('codex missing')
                return subprocess.CompletedProcess(argv,0,'/test/ringer\n','')
            out=io.StringIO()
            with patch('refresh_codex.resolve_sources',return_value={}),patch('refresh_codex.subprocess.run',side_effect=run),redirect_stdout(out):
                rc=connection_report(library,registry,root)
            self.assertEqual(rc,1)
            self.assertIn('Cannot inspect Codex plugins',out.getvalue())
            self.assertIn('FileMaker/ADT local endpoint:',out.getvalue())
            self.assertIn('Ringer clone:',out.getvalue())

    def test_batch_validation_failure_leaves_live_packages_untouched(self):
        from unittest.mock import patch
        from refresh_codex import promote
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'staged';live=root/'live';packages=[]
            for name in ['pm','fm-dc']:
                package=stage/name;package.mkdir(parents=True);(package/'new').write_text('new');packages.append(package)
                dest=live/name;dest.mkdir(parents=True);(dest/'.dc-codex-build.json').write_text('{}');(dest/'old').write_text(name)
            with patch('refresh_codex.subprocess.run',side_effect=[subprocess.CompletedProcess([],0),subprocess.CalledProcessError(1,[]) ]):
                with self.assertRaises(subprocess.CalledProcessError):promote(packages,live,root)
            for name in ['pm','fm-dc']:
                self.assertEqual((live/name/'old').read_text(),name)
                self.assertFalse((live/name/'new').exists())

if __name__ == "__main__":
    unittest.main()
