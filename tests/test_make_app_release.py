"""make-app.sh --release refuses before it builds anything (spec: docs/specs/app-updates.md).

Each test runs a copy of make-app.sh inside a throwaway git repo, so no swift build, no signing and no
publish happens: every case here must stop at a refusal.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "factory" / "app" / "make-app.sh"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    app = root / "factory" / "app"
    app.mkdir(parents=True)
    shutil.copy(SCRIPT, app / "make-app.sh")
    (app / "VERSION").write_text("1.2.3\n")
    (app / "sparkle-public-key").write_text("PUBKEY\n")
    (app / ".gitignore").write_text("build/\n.build/\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, capture_output=True)
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-q", "origin", "main")
    # a gh that is signed in unless FAKE_GH_SIGNED_OUT, and says whether the release exists, per FAKE_TAG_EXISTS
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text('#!/bin/sh\n[ "$1 $2" = "auth status" ] && { [ -n "$FAKE_GH_SIGNED_OUT" ] && exit 1; exit 0; }\n'
                  '[ "$1 $2" = "release view" ] && [ -n "$FAKE_TAG_EXISTS" ] && exit 0\nexit 1\n')
    gh.chmod(0o755)
    return root


def release(repo, *flags, **env):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("RUNWAY_", "SPARKLE_"))}
    e["PATH"] = f"{repo.parent / 'bin'}:{e['PATH']}"
    e.update({"RUNWAY_SIGN_IDENTITY": "Developer ID Application: Test (X)", "RUNWAY_NOTARY_PROFILE": "p",
              "RUNWAY_RELEASE_CHECK_CMD": "true"})
    e.update(env)
    return subprocess.run(["bash", str(repo / "factory/app/make-app.sh"), "--release", *flags],
                          capture_output=True, text=True, env=e)


def test_refuses_dirty_tree(repo):
    (repo / "stray.txt").write_text("x")
    r = release(repo)
    assert r.returncode != 0 and "working tree is dirty" in r.stderr


def test_refuses_branch_that_is_not_main(repo):
    git(repo, "checkout", "-q", "-b", "feature")
    r = release(repo)
    assert r.returncode != 0 and "not on main" in r.stderr


def test_refuses_existing_tag(repo):
    r = release(repo, FAKE_TAG_EXISTS="1")
    assert r.returncode != 0 and "runway-app-v1.2.3 already exists" in r.stderr


def test_refuses_local_tag_with_no_release(repo):
    git(repo, "tag", "runway-app-v1.2.3")
    r = release(repo)
    assert r.returncode != 0 and "runway-app-v1.2.3 already exists as a local git tag" in r.stderr


def test_refuses_remote_tag_with_no_release(repo):
    git(repo, "tag", "runway-app-v1.2.3")
    git(repo, "push", "-q", "origin", "runway-app-v1.2.3")
    git(repo, "tag", "-d", "runway-app-v1.2.3")
    r = release(repo)
    assert r.returncode != 0 and "runway-app-v1.2.3 already exists as a tag on origin" in r.stderr


def test_refuses_when_origin_cannot_be_checked(repo):
    git(repo, "remote", "set-url", "origin", str(repo.parent / "missing.git"))
    r = release(repo)
    assert r.returncode != 0 and "could not check origin" in r.stderr


def test_refuses_signed_out_gh(repo):
    r = release(repo, FAKE_GH_SIGNED_OUT="1")
    assert r.returncode != 0 and "gh is missing or not signed in" in r.stderr


def test_refuses_when_check_fails(repo):
    r = release(repo, RUNWAY_RELEASE_CHECK_CMD="false")
    assert r.returncode != 0 and "check failed" in r.stderr


def test_missing_signing_identity_fails_clearly(repo):
    r = release(repo, RUNWAY_SIGN_IDENTITY="")
    assert r.returncode != 0 and "RUNWAY_SIGN_IDENTITY" in r.stderr


def test_real_release_needs_notary_profile(repo):
    r = release(repo, RUNWAY_NOTARY_PROFILE="")
    assert r.returncode != 0 and "RUNWAY_NOTARY_PROFILE" in r.stderr


def test_missing_public_key_fails_clearly(repo):
    (repo / "factory/app/sparkle-public-key").unlink()
    git(repo, "commit", "-q", "-am", "drop key")
    r = release(repo)
    assert r.returncode != 0 and "sparkle-public-key" in r.stderr


def test_dry_run_reports_branch_problems_but_does_not_stop_on_them(repo):
    # an agent's worktree is never on main; the dry run notes it and goes on (and here stops at the missing key)
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / "factory/app/sparkle-public-key").unlink()
    git(repo, "commit", "-q", "-am", "drop key")
    r = release(repo, "--dry-run")
    assert "would refuse: not on main" in r.stderr and "sparkle-public-key" in r.stderr
