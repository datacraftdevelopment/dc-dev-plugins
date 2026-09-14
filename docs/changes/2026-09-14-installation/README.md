# Local installation verification — 14 September 2026

Reviewed implementation: library `f5e569e`, plugins `82cf559`; earlier compatibility baseline `d7396fc`. These are local commits; no push or publication was performed.

## Installed release

Five source plugins were installed in Claude Code from the local `dc-dev-plugins` marketplace: PM 0.18.0, design-dc 0.2.2, ui-test 0.3.0, fm-dc 0.8.1 and basecamp-dc 0.1.1. fm-dc remains disabled in Claude, matching the previous preference. Superseded PM/design/fm registrations from `dc-plugins` were removed with data retained. The public marketplace and unrelated plugins remain registered.

Nine generated Codex plugins were refreshed and enabled: those five plus Ringer, dc-workflow, filemaker-agentic-development and adt-standards-default. Every source file in each generated package was compared with its installed cache. The five Claude caches were compared with tracked source files. Canonical Claude Ringer/build-swarm/cross-review skill links and routing outside managed sections were checked. No verification errors remain.

See [the complete installation inventory](installation-verification.json), [connection report](connection-check-final.log) and [host versions](host-versions.json).

## Inventory observations

The first inventory comparison flagged unrelated entries. Inspection showed that Codex CLI 0.154.0 now applies the personal-marketplace filter to installed results; an unfiltered inventory confirms unrelated Codex installations are unchanged. Seven unrelated official Claude plugins carry earlier update timestamps around 09:26 UTC, preceding the DataCraft install around 11:46 UTC. Their observed version changes are retained in the report rather than rolled back or described as unchanged. All unrelated Claude scope/enabled preferences remain unchanged.

## Host versions and limits

Codex CLI was updated through its npm installation to 0.154.0. Claude Code's native updater moved 2.1.260 to 2.1.270. Ringer review workers ran successfully afterward. New Codex tasks and restarted Claude Code sessions are required to load refreshed instructions; the active desktop app was not restarted.

Computer-use access to the Codex desktop app was denied, so its version/update status remains unverified. Automatic approval review also blocked the localhost UI pilot: no screenshots, UI mutations or saved-state proof were obtained, and its disposable server is stopped. Code/schema tests do not establish visual truth or authenticate human evidence. The local FileMaker/ADT endpoint is offline; database access and optional external integrations were not tested.

## Read the workflow

The [HTML workflow guide](../../workflow-guide.html) explains the planning, technical resolution, frontend checkpoints, autonomous build, multimodal acceptance and session-continuity flow. See the [release notes](../2026-09-14-shared-workflow.md) and [Ringer audit](../../reviews/2026-09-14-shared-workflow/README.md) for implementation detail.
