"""apple-dc: the manifest, the skills, the scaffold, the release script's refusals and the icon cutter.

Nothing here builds Swift or signs anything: those need a Mac. The scaffold and make-app.sh's refusals run anywhere.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'apple-dc'
NEW_APP = PLUGIN / 'scripts/new-app.py'
SKILLS = {'app-support', 'new-apple-app', 'app-icon', 'mac-release', 'app-store'}
sys.path.insert(0, str(ROOT / 'scripts'))


def git(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)


def new_repo(base: Path) -> Path:
    repo = base / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'config', 'user.email', 't@example.com')
    git(repo, 'config', 'user.name', 't')
    return repo


def scaffold(repo: Path, kind: str, *extra: str) -> subprocess.CompletedProcess:
    args = ['--name', 'Tally', '--display', 'Tally Counter', '--bundle-id', 'dev.example.tally']
    args += ['--release-repo', 'example/tally', '--owner', 'Example Ltd'] if kind == 'mac' else ['--team', 'ABCDE12345']
    return subprocess.run([sys.executable, str(NEW_APP), kind, '--repo', str(repo), *args, *extra],
                          capture_output=True, text=True)


class ManifestTests(unittest.TestCase):
    def test_listed_and_claude_only(self):
        market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        entry = [p for p in market['plugins'] if p['name'] == 'apple-dc']
        self.assertEqual(entry[0]['source'], './apple-dc')
        manifest = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        self.assertEqual(manifest['name'], 'apple-dc')
        import build_codex
        self.assertIn('apple-dc', build_codex.CLAUDE_ONLY)

    def test_skills_have_frontmatter(self):
        self.assertEqual({p.name for p in (PLUGIN / 'skills').iterdir()}, SKILLS)
        for name in SKILLS:
            text = (PLUGIN / 'skills' / name / 'SKILL.md').read_text()
            front = re.match(r'---\nname: (.+)\ndescription: (.+)\n---\n', text)
            self.assertIsNotNone(front, name)
            self.assertEqual(front.group(1), name)
            self.assertLess(len(front.group(2)), 1024, name)

    def test_nothing_personal_ships(self):
        # The repo is public: team IDs, profile names, machine names and home paths live in the app-support notebook.
        pattern = re.compile(r'/Users/(?!someone\b)|FUB46|runway-notary|[A-Za-z]-notary\b|Joe-M6|mini-m4|YoJoe|ClipBoard|Scrapbench')
        for path in PLUGIN.rglob('*'):
            if path.is_file():
                hits = pattern.findall(path.read_text(errors='ignore'))
                self.assertEqual(hits, [], path)

    def test_shell_scripts_parse(self):
        for script in ('templates/mac/make-app.sh', 'templates/ios/ship.sh', 'scripts/doctor.sh'):
            r = subprocess.run(['bash', '-n', str(PLUGIN / script)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f'{script}: {r.stderr}')


class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = new_repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_mac_menu_bar_app(self):
        r = scaffold(self.repo, 'mac')
        self.assertEqual(r.returncode, 0, r.stderr)
        app = self.repo / '_mac'
        for rel in ('Package.swift', 'app.env', 'make-app.sh', 'RELEASING.md', 'VERSION', '.gitignore',
                    'Sources/Tally/TallyApp.swift', 'Sources/Tally/AppUpdater.swift',
                    'Sources/Tally/MoveToApplications.swift', 'Sources/TallyCore/AppLocation.swift',
                    'Tests/TallyCoreTests/AppLocationTests.swift', 'release-notes/0.1.0.md'):
            self.assertTrue((app / rel).is_file(), rel)
        self.assertFalse((app / 'Sources/Tally/App.menubar.swift').exists())
        self.assertIn('MenuBarExtra', (app / 'Sources/Tally/TallyApp.swift').read_text())
        env = (app / 'app.env').read_text()
        self.assertIn('APP_MENU_BAR=1', env)
        self.assertIn('APP_SPARKLE_ACCOUNT="tally"', env)
        self.assertIn('Example Ltd', env)
        self.assertTrue(os.access(app / 'make-app.sh', os.X_OK))
        workflow = (self.repo / '.github/workflows/mac.yml').read_text()
        self.assertIn('working-directory: _mac', workflow)
        self.assertIn('example/tally', workflow)
        for path in [*app.rglob('*'), self.repo / '.github/workflows/mac.yml']:
            if path.is_file():
                self.assertNotRegex(path.read_text(errors='ignore'), r'__[A-Z_]+__', path)

    def test_mac_window_app(self):
        r = scaffold(self.repo, 'mac', '--window', '--dir', 'app')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('WindowGroup', (self.repo / 'app/Sources/Tally/TallyApp.swift').read_text())
        self.assertIn('APP_MENU_BAR=0', (self.repo / 'app/app.env').read_text())

    def test_ios_app(self):
        r = scaffold(self.repo, 'ios')
        self.assertEqual(r.returncode, 0, r.stderr)
        app = self.repo / '_ios'
        self.assertIn('DEVELOPMENT_TEAM: ABCDE12345', (app / 'project.yml').read_text())
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER: dev.example.tally', (app / 'project.yml').read_text())
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER: dev.example.tally.tests', (app / 'project.yml').read_text())
        self.assertIn('GENERATE_INFOPLIST_FILE: YES', (app / 'project.yml').read_text())
        self.assertIn('<string>ABCDE12345</string>', (app / 'ExportOptions.plist').read_text())
        self.assertTrue((app / 'Sources/TallyApp.swift').is_file())
        self.assertTrue((app / 'Resources/PrivacyInfo.xcprivacy').is_file())
        self.assertTrue(os.access(app / 'ship.sh', os.X_OK))

    def test_refuses_existing_folder_and_bad_names(self):
        (self.repo / '_mac').mkdir()
        r = scaffold(self.repo, 'mac')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('already exists', r.stderr)
        r = subprocess.run([sys.executable, str(NEW_APP), 'mac', '--repo', str(self.repo), '--dir', 'x',
                            '--name', 'my app', '--bundle-id', 'dev.example.x', '--release-repo', 'a/b'],
                           capture_output=True, text=True)
        self.assertIn('Swift type name', r.stderr)
        r = subprocess.run([sys.executable, str(NEW_APP), 'ios', '--repo', str(self.repo),
                            '--name', 'Tally', '--bundle-id', 'dev.example.x'], capture_output=True, text=True)
        self.assertIn('--team is required', r.stderr)


class MakeAppRefusalTests(unittest.TestCase):
    """Every case stops before `swift build`, so these run without a Mac."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = new_repo(self.tmp)
        self.assertEqual(scaffold(self.repo, 'mac').returncode, 0)
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'init')
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        gh = self.bin / 'gh'
        gh.write_text('#!/bin/sh\n[ "$1 $2" = "auth status" ] && exit 0\n'
                      '[ "$1 $2" = "release view" ] && [ -n "$FAKE_TAG_EXISTS" ] && exit 0\nexit 1\n')
        gh.chmod(0o755)
        # A swift that fails loudly: reaching it means a refusal was missed.
        swift = self.bin / 'swift'
        swift.write_text('#!/bin/sh\necho "REACHED SWIFT" >&2\nexit 99\n')
        swift.chmod(0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def release(self, *flags, **env):
        e = {k: v for k, v in os.environ.items() if not k.startswith(('APP_', 'SPARKLE_'))}
        e['PATH'] = f'{self.bin}:{e["PATH"]}'
        e.update({'APP_SIGN_IDENTITY': 'Developer ID Application: Test (X)', 'APP_NOTARY_PROFILE': 'p',
                  'APP_RELEASE_CHECK_CMD': 'true'})
        e.update(env)
        return subprocess.run(['bash', str(self.repo / '_mac/make-app.sh'), *flags], capture_output=True,
                              text=True, env=e)

    def test_option_mistakes(self):
        self.assertIn('only goes with --release', self.release('--dry-run').stderr)
        self.assertIn("don't mix", self.release('--open', '--release').stderr)

    def test_refuses_dirty_tree(self):
        (self.repo / 'stray.txt').write_text('x')
        r = self.release('--release')
        self.assertIn('working tree is dirty', r.stderr)
        self.assertNotIn('REACHED SWIFT', r.stderr)

    def test_refuses_branch_that_is_not_main(self):
        git(self.repo, 'checkout', '-q', '-b', 'feature')
        r = self.release('--release')
        self.assertIn('not on main', r.stderr)
        self.assertNotIn('REACHED SWIFT', r.stderr)

    def test_refuses_without_identity_or_sparkle_key(self):
        r = self.release('--release', APP_SIGN_IDENTITY='')
        self.assertIn('APP_SIGN_IDENTITY is not set', r.stderr)
        r = self.release('--release')
        self.assertIn('sparkle-public-key is missing', r.stderr)
        self.assertNotIn('REACHED SWIFT', r.stderr)

    def test_refuses_existing_release(self):
        (self.repo / '_mac/sparkle-public-key').write_text('PUBKEY\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'key')
        r = self.release('--release', FAKE_TAG_EXISTS='1')
        self.assertIn('v0.1.0 already exists as a GitHub release', r.stderr)
        self.assertNotIn('REACHED SWIFT', r.stderr)

    def test_dry_run_carries_on_to_the_build(self):
        r = self.release('--release', '--dry-run', APP_SIGN_IDENTITY='')
        self.assertIn('would refuse: sparkle-public-key is missing', r.stderr)
        self.assertIn('REACHED SWIFT', r.stderr)


try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipIf(Image is None, 'Pillow is not installed')
class IconTests(unittest.TestCase):
    def test_mac_tile_and_opaque_ios_icon(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            Image.new('RGBA', (1200, 1200), (200, 40, 40, 255)).save(tmp / 'art.png')
            r = subprocess.run([sys.executable, str(PLUGIN / 'scripts/make-icons.py'), str(tmp / 'art.png'),
                                '--mac', str(tmp / 'mac.png'), '--ios', str(tmp / 'AppIcon.appiconset'),
                                '--web', str(tmp / 'web')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            mac = Image.open(tmp / 'mac.png')
            self.assertEqual(mac.size, (1024, 1024))
            self.assertEqual(mac.getpixel((40, 40))[3], 0)        # margin outside the tile
            self.assertEqual(mac.getpixel((110, 110))[3], 0)      # cut corner of the tile
            self.assertEqual(mac.getpixel((512, 512))[3], 255)    # inside the tile
            ios = Image.open(tmp / 'AppIcon.appiconset/AppIcon.png')
            self.assertEqual((ios.size, ios.mode), ((1024, 1024), 'RGB'))
            contents = json.loads((tmp / 'AppIcon.appiconset/Contents.json').read_text())
            self.assertEqual(contents['images'][0]['filename'], 'AppIcon.png')
            self.assertEqual(Image.open(tmp / 'web/apple-touch-icon.png').size, (180, 180))


if __name__ == '__main__':
    unittest.main()
