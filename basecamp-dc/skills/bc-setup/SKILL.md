---
name: bc-setup
description: "Opt this repo into the Basecamp client face — verify the existing .basecamp/config.json and install docs/agents/client-face.md from the bundled template if (and only if) it is absent. Use when the user says \"set up Basecamp for this repo\", \"opt into the client face\", \"install the client-face contract\", or right after the basecamp CLI's config was added to a repo. Purely local: never creates or edits .basecamp/config.json, never calls Basecamp, never overwrites an existing client-face.md."
---

# bc-setup — one local file, only when asked

Opting in is two facts on disk: the basecamp CLI's `.basecamp/config.json`
(which this skill **requires but never creates** — no config, no setup) and
`docs/agents/client-face.md`, the contract the pm plugin's `stepping-away`
reads at session close. This skill installs only the second, from the bundled
template. Everything is offline; nothing talks to Basecamp.

## Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bc_setup.py" --root .
```

- **Exit 0** — installed, or already present and left untouched (hand edits
  always win; rerunning is safe and changes nothing).
- **Exit 1** — no valid `.basecamp/config.json`. Stop. The user sets the CLI
  up first (`basecamp setup`; ids per the `bc-client-face` config contract).
  Do not generate the config or invent ids.
- **Exit 2** — a destination/path conflict or write error prevented setup; report the exact error. Existing files remain hand-owned.

## After install

- The contract routes session-close work to `bc-close-out` by name and spells
  out fully shipped / partly shipped / ticketless / missing mapping. It is the
  user's file now — point them at it rather than re-editing it yourself.
- Optionally check the ids the close-out needs:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bc_config.py" --require shipped,what_shipped,project_id`
