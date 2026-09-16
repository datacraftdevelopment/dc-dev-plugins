---
name: adt-webviewer
description: >
  Use when building or maintaining an HTML/React app inside a FileMaker file with ADT —
  "web viewer app", "HTML layout", "dashboard in FileMaker", adt app add, adt layout
  add, adt typegen, adt deploy, the @adt/fmdapi typed clients, or the window.FileMaker
  data path. Also use when the scaffold's pnpm install fails (trust-policy /
  ERR_PNPM_TRUST_DOWNGRADE), when deploy times out, or when comparing ADT's web viewer
  pipeline to ProofKit. No ProofKit needed — ADT does this end to end on its own.
---

# Web viewer apps — HTML layouts through ADT, end to end

ADT builds React apps that live *inside* the `.fmp12` and read/write its data —
no ProofKit, no FileMaker Server, no network listener beyond the file. ADT
vendors its own fork of the fmdapi machinery (`@adt/fmdapi`), so if you know
ProofKit, the architecture is familiar but self-contained.

## The loop

```
adt app add <name>        # scaffold + provision + FileMaker layout
pnpm install
adt layout add --table <T> --layout API_<T> --fields "..."   # per table
<write the React app>
pnpm build                # vite + singlefile → ONE dist/index.html
adt deploy                # push the HTML into the file
```

### `adt app add` does in one run

- Scaffolds `webviewer-apps/<name>`: React + TypeScript + Vite + Tailwind +
  TanStack Router (**hash history — required inside a web viewer**) + React
  Query + zod + `@adt/fmdapi` (vendored at `vendor/`, not from npm), plus a
  workspace `package.json`/`pnpm-workspace.yaml` at the project root.
- Creates the FileMaker layout carrying the app's web viewer.
- Runs install/typegen/lint/commit — and if a phase fails, the **phase ledger**
  (`adt-project-setup-summary.json` + `project-setup.log`) records exactly what
  ran/failed/skipped with per-phase fix commands. Recovery = run those; never
  re-scaffold.

### `adt layout add` — typed clients per table

One command per table: creates the `API_<Table>` layout with the named fields,
registers it in `adt.config.json`, runs typegen, and warns which fields are
calc/summary (**read-only through the Data API**). `--update` re-lays-out the
generated objects and leaves hand-added ones alone. Typegen emits a zod schema,
an inferred type, and a ready client (`list/find/create/update/delete` + more)
wired to `WebViewerAdapter({ scriptName: "ADT_execute_data_api" })`. Find
queries use Data API syntax (`{ ContactID: "==<uuid>" }`); `ignoreEmptyResult`
turns no-matches into `[]`.

### The runtime data path

Browser JS → `window.FileMaker` bridge → `ADT_execute_data_api` script →
FileMaker's local **Execute FileMaker Data API** step → callback into the web
viewer. The same script serves the MCP data tools — one data plane, two
consumers. Auto-enter fields (UUIDs, timestamps) fire normally; unstored calcs
are evaluated by FileMaker, not JS.

### Deploy

`vite build` (singlefile plugin) inlines everything into one `dist/index.html`;
`adt deploy` stores it in ADT Persistent Data (the provisioned `ADT` table's
global `AppName` selects which app the "ADT App" layout shows). Deploy normally
needs the live handshake and can hit the connector-wedge timeout — force-refresh
clears it (see `adt-connections`). **Fallback:** the HTML also deploys over the
schema lane via `update:persistentData` (key `ADT`, instance = app name) — no
handshake, lock-proof.

## The pnpm trust-policy gotcha

pnpm 10 hardening policies can block the scaffold's install — observed twice:
`trust-policy=no-downgrade` refusing `semver@6.3.1`
(`ERR_PNPM_TRUST_DOWNGRADE`), then `blockExoticSubdeps` blocking tailwindcss.
Fix that preserves the global policy: workspace-level `.npmrc` overrides, e.g.
`trust-policy-exclude[]=semver@6.3.1`. Noise you can ignore: engine warnings
(scaffold wants Node 22/24) and husky's ".git can't be found" when the
workspace nests inside an outer repo.

## Preview

Web viewer apps have a real browser feedback loop — preview in the browser and
fix errors before deploying. (Native layouts have no equivalent; that is what
FM Lens snapshot loop is for — see `adt-native-layouts`.)
