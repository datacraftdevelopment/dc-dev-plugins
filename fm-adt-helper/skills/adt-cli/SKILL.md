---
name: adt-cli
description: >
  Use when setting up or managing an ADT project with the `adt` CLI — creating a project
  (adt init), recording a hosted or local file (adt connect), provisioning or checking
  ADT's components in a file (adt components status/apply/reconcile), scaffolding a web
  viewer app (adt app add), creating Data API layouts (adt layout add), regenerating
  typed clients (adt typegen), pushing HTML (adt deploy), or diagnosing system/project
  health (adt doctor). Also use when adt "isn't found" (it is deliberately off PATH),
  when reading or editing adt.json, or when interpreting doctor output and its
  notDiagnosed narrowing.
---

# The `adt` CLI — project orchestration

`adt` scaffolds and manages ADT projects; the heavy lifting on `.fmp12` files is
delegated to the `fm` engine underneath. It is **deliberately not on PATH** in
0.4.0 — Claude Code gets it through the Claris plugin; from a shell, it lives at
`~/Library/Application Support/ADT/MCP/bin/adt` (also in the plugin cache's
`bin/`). "command not found: adt" is policy, not breakage.

## Command map (0.4.0) — authoritative source is `adt --help` on the machine

| Command | Does |
|---|---|
| `adt init [dir]` | Create project: `adt.json`, AGENTS.md, CLAUDE.md, `.claude/skills/fm-cli/`, .gitignore, git repo. **Non-destructive** — keeps an existing CLAUDE.md and says so; refuses only a folder that already has `adt.json` |
| `adt connect "<target>"` | Record a file in adt.json, confirming credentials (native prompt if needed). Repeatable; `--suggest` lists what FileMaker Pro has open |
| `adt components status/apply/reconcile/remove` | ADT's tooling in the file: inspect, provision, upgrade, uninstall. Renamed from `adt addon` in 0.4.0. Apply works with **zero Pro cooperation** (goes through fm over fmnet) |
| `adt app add <name>` | Scaffold `webviewer-apps/<name>` + provision + create the FileMaker layout (see `adt-webviewer`) |
| `adt layout add` | One command: create a Data API layout, register it in `adt.config.json`, run typegen. The right way to make API layouts |
| `adt typegen` | Regenerate typed clients from layout metadata |
| `adt deploy` | Push built HTML into the file |
| `adt doctor [--json]` | System + project health; auto-starts the connector script for recorded files (`--no-auto-connect` to skip) |
| `adt agents detect/list` · `install/uninstall` · `logs` · `update` · `mcp` | MCP-client detection, machine install, installer logs, vendored-package updates, stdio MCP server |

`--wizard`, `--completions`, `--log-level` exist everywhere; `--ci` /
`--non-interactive` are accepted-but-no-op (nothing prompts except connect's
native credential window).

## adt.json anatomy

Written by `adt init`; the map from **file name → target address**
(`fmnet://host/Name` or a local `.fmp12` path). Holds account names, **never
passwords** (those go to the keychain via the native prompt). Recording a file
that isn't reachable yet is fine — "Recorded, but not reachable yet" with the
exact per-file sharing fix; connect failure ≠ init failure. A credential-free
file gets no account entry at all.

## What `components apply` provisions (bundle 0.3.1)

1 table (`ADT`, one global `AppName` field), 3 custom functions, ~20 scripts in
an "Agentic Development Toolkit" folder (`Connect To ADT`, `ADT_probe`,
`ADT_execute_sql`, `ADT_execute_data_api[_on_server]`, `ADT_deploy_html`,
`ADT_container_upload`, …), and the connector layouts (`ADT App`,
`ADT MCP Connector`). The bundle is versioned separately from the CLI; doctor
compares the file against the *shipped* bundle version. Note: 0.4.0's
`components remove` is broken on a vanilla provisioned file (dependency order;
rolls back safely) — apply/reconcile are fine.

## Reading the doctor

- It **narrows honestly**: with no web viewer app it skips Node-toolchain
  checks and reports `notDiagnosed` with the reason and the widening command.
  Naming a file (`--file`) widens file checks regardless. `notDiagnosed` means
  unknown, not ready.
- Doctor "ready" ≠ data tools working — its probes ride a lighter path than the
  data tools' callback socket. If tools time out anyway, see `adt-connections`.
- Raw telemetry without any MCP session:
  `GET http://127.0.0.1:1366/health` — plugin alive, FileMaker idle state, last
  script-start errorCode.
- After a failed `adt app add`, the phase ledger
  (`adt-project-setup-summary.json`, `adt doctor --setup-log --phase <id>`)
  names each phase's status and fix commands. **Never re-scaffold to recover.**
