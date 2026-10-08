---
name: credential-guard
description: What the sdlc credential-guard hook blocks and how to work with it. Use when a git command is refused with "credential-guard: BLOCKED", when staging or committing files that might hold secrets, or when asked whether a credential file is protected.
---

# Credential guard

The sdlc plugin installs a `PreToolUse` hook on Bash
(`hooks/credential-guard.sh`, logic in `scripts/credential_guard.py`). It runs
on every machine that has the plugin, in every repo, with no setup. Unlike
`gate-hooks`, nothing is copied into the repo.

## What it blocks

`git add`, `git stage` and `git commit` when a credential-shaped file would be
staged or committed: `.env` and `.env.*`, key and certificate files, and the
other patterns in `scripts/credential-policy.json`. It follows literal
directory changes, scoped subshells, explicit commit paths, forced adds and
quoted or chained `-C` paths. Example and template files (`*.example`,
`*.sample`) pass. Removing a tracked credential is allowed.

It blocks rather than guesses: a git command it cannot inspect safely (looped,
wrapped in `xargs` or `sh -c`, or a pipeline or background job that stages,
commits or changes the repository) is refused with an explanation. Read-only git
(`status`, `log`, `diff`, `show`, `ls-files`, `branch` and the rest of its
read-only list) may be piped or backgrounded (sdlc 0.2.1). Unrelated commands and
folders that aren't repos pass.

## When it blocks you

1. Read the message. It names the file or the reason.
2. If a credential file really was about to be staged, add it to `.gitignore`
   and stage the paths you meant by name instead of `git add .` or `-A`.
3. If the command was refused because it couldn't be inspected, split it: one
   plain git command per line, with literal paths and `git -C <path>` instead of
   `cd … &&`.
4. Never work around it with another tool or a script. If the policy is wrong,
   say so and propose the change to `credential-policy.json`.

## Limits

It protects tool invocations, not arbitrary subprocesses or file contents. A
secret pasted into a source file is not caught. Unattended runs (Runway) get the
same protection, as long as the sdlc plugin is installed on that machine.

## Maintaining it

Run `bash hooks/test-credential-guard.sh` and
`python3 -m pytest tests/test_sdlc_credential_guard.py -q` from the
marketplace root after any change. build-swarm keeps a snapshot of the policy:
check parity with `python3 scripts/sync_pm_policy.py --build-swarm <source-dir> --check`.
