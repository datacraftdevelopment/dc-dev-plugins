---
name: app-support
description: The app-support notebook every apple-dc skill reads before it builds, signs or ships a Mac or iOS app, and writes to afterwards (apps.md, machine.md, lessons.md). Use when another apple-dc skill says to, when the user says "record that lesson", "what do we know about building apps", "promote lessons", or "set up app support", or when a Mac or iOS build, signing, notarization or upload just failed or was worked around.
---

# App support: the notebook that makes each app easier than the last

Every app teaches something (a certificate that expired, a notary profile a password reset broke, a Gatekeeper
quirk). This plugin keeps the generic how-to; the **app-support folder** keeps what is true for this person, their
Macs and their apps, plus fresh lessons not yet folded into the plugin. It lives outside every app repo, and it is
private: it names signing identities, profiles and apps. Never put a secret in it (no passwords, `.p8`, `.p12` or
private keys); write where the secret lives instead.

## Find it

1. Read `~/.apple-dc.json` (`{"app_support": "<absolute path>"}`).
2. Missing: ask the user once where their app-support folder is (offer to create one), then write that file.
3. A new folder: copy `${CLAUDE_PLUGIN_ROOT}/templates/app-support/*` into it. If the user wants it on more than one
   Mac, make it a private git repo (never public) and commit after each change.

## Before any apple-dc work

Read `apps.md` (the app's own section), `machine.md` (this Mac's section) and `lessons.md` (all of it: it is short on
purpose). A lesson outranks this plugin's skills where they disagree; say so, and offer to promote it (below).

`machine.md` goes stale the moment a password is reset or a certificate expires. Before a release or upload, refresh
this Mac's section from `bash ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh --notary <each profile listed>`, not from what
the file says.

## After it

- **A new fact about an app or a Mac** (new bundle ID, a notary profile created, version shipped): update its section.
- **Something went wrong, or a workaround was found:** add a line at the top of `lessons.md`:
  `- YYYY-MM-DD (<app>): what happened, and what to do instead.` One line, specific, no story.
- Commit if the folder is a git repo.

Do this in the same turn it happens. The next app's session will not remember it otherwise.

## Promote lessons

When the user asks, or when `lessons.md` has grown by five or so lines since the last promotion:

1. Pick lessons that are generic (true for anyone shipping Apple apps) and name nothing private: no client, team ID,
   profile names, people or paths.
2. Fold each into the plugin skill or template it belongs to, in the dc-dev-plugins repo, as a PR that bumps
   `apple-dc`'s version. The plugin repo is public: re-read each line for anything private before it goes.
3. Mark each promoted line in `lessons.md` with `(promoted)`; keep it, so the history stays.

Personal facts (which Mac holds which key, which profile an app uses) never leave the notebook.
