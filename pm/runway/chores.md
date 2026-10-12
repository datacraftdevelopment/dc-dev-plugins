# Chores

`chores.json` lists the machine chores the Runway app offers as buttons, so Joe
doesn't open Terminal for them (spec: `docs/specs/app-chores.md`). The app reads
the file from the engine checkout in its Scripts setting; a new chore is an edit
here, not an app release. It is data: the app runs the listed command and
nothing else.

Each entry:

| Field | Meaning |
|---|---|
| `id` | Unique, kebab-case. |
| `title` | The button's name. |
| `why` | One line the app shows under it. |
| `run` | The shell line, run through `/bin/zsh -lc` in the window's terminal pane. `{runway}`, `{repo}` and `{checkout}` are replaced with the shell-quoted `runway.py` path, the loop's repo and the engine checkout. |
| `cwd` | `checkout` (the engine checkout: the chore shows in the This Mac sheet) or `repo` (each loop's repo: the chore shows in that project's menu). |
| `show_if` | Optional. A status command run the same way, at most 10 seconds, never a model call. Exit 0 shows the chore; anything else hides it. |
| `confirm` | Optional. `true` asks once more before running. |

The app always shows the command and where it runs before the first click. After
the tab's process exits it runs `show_if` again and says whether the chore is
still needed.

A chore never loads or unloads a LaunchAgent, changes a worker's permissions or
`agent_cmd`, or touches a repo other than the one it names. Those stay deliberate
steps.
