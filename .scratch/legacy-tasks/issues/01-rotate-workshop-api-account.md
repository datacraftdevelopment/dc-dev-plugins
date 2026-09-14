# 01 — Rotate the workshop `api` account if it is still live

**What to build:** nothing to build — an operational step. The credentials scrubbed from fm-dc in commit 36c9f47 (v0.5.3, 2026-07) remain in git history and in every install made before the scrub. If the workshop FileMaker file's `api` account is still live, rotate its password and update wherever it is used.

**Type:** research

**Blocked by:** none

**Waiting on:** Joe — is the workshop `api` account still live, and where is the workshop file hosted now? (since 2026-09-13; carried from `_pm/TASKS.md`, 2026-07-15)

**Status:** needs-human

- [ ] Joe confirms live or retired
- [ ] if live: password rotated, every consumer updated, old value confirmed dead

## Comments

- 2026-09-13 · carried from `_pm/TASKS.md` under MIGRATION-0.17. Conditional and security-relevant, so it stays live as a waiting ticket rather than an inbox line.
