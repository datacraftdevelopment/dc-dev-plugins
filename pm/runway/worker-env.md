# Worker environment

What a fresh Runway worktree of this repo lacks, and how a headless ticket run
should work here. Runway's ticket prompt tells every run to read this file first.
Keep it short and current; the retro is where gaps show up.

## Missing from a fresh worktree

- Env files: <e.g. copy `.env` from the main checkout, or "none needed">
- Dependencies: <e.g. `npm ci`, `pip install -r requirements.txt`, or "none">
- Local data: <e.g. seed the test database with `make seed`, or "none">

## Verify

<The command a run should use to check its own work, e.g. `python3 -m pytest -q`.
Usually the same as `check_cmd` in runway.json.>

## Leave alone

<Paths a ticket run must not edit, e.g. `vendor/`, generated files, migrations
already applied in production.>
