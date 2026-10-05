# Quirks from running the factory inside Claude Code Projects

> Observed 2026-10-05 while building and running experiment 01 from a Projects thread. Projects is in beta, so any of these may change. Each entry says what happened, why it matters for a factory, and the workaround used.

## How the pieces were wired

- **Coordinator:** the project's chat session. It started this thread with a brief and relayed Joe's later project-chat question into it.
- **Thread:** a cloud container. It reached the Mac in two ways:
  - **Folder tools:** a Linux VM on the Mac that sees only the connected folders.
  - **Remote Control (RC):** a real Claude Code session on the Mac, in one folder, with Joe's CLI and login.
- **RC → thread:** RC reported back to the thread by cross-session message. Joe's messages in the thread reached both the thread and the RC session.

## Access and routing

1. **Folder tools and Remote Control can't run at once.** While the RC session was active, the thread's folder tools were withheld. Factory impact: a thread can't run work on the Mac and record results in the repo at the same time. Workaround: stop RC, then write.
2. **Write access went missing after RC stopped.** Stopping RC should have brought the folder tools back. Instead they came back blocked by a permission deny rule for about 8 minutes, so the results couldn't be written when the run finished. They returned without anyone changing anything. Cause unknown **(unverified)**. Factory impact: the "record results" step can silently stall. Treat recording as its own ticket so it can't be lost.
3. **The folder VM can't run your tools.** It has no `claude` CLI, no login, and no Ringer or Codex. Anything that runs agents needs RC.
4. **The folder VM only writes inside connected folders.** The practice repo couldn't go to `~/Agentic-Mini/_Tools/runway-practice` as planned, so it went in `SoftwareFactory/sandbox/` (gitignored) instead.
5. **Pushing files from the cloud container failed.** `device_commit_files` returned 404 for files staged in the container. Workaround: send a base64 tarball through `device_bash`. It's clumsy, but it works up to a few tens of KB per call.
6. **No connector, no tracker.** The Linear connector's sign-in had expired, so threads can't read or write Linear until it's reconnected. That matters if Linear becomes the tracker.

6a. **The first folder binding didn't match the brief** (seen from the coordinator side). The thread was started for the SoftwareFactory folder, but its first device connection reported using `_Core/_Plugins`, the project's other approved folder. Work went to the right place in the end, but a factory thread should confirm which folder it's bound to before it writes anything.

## Git in the folder VM

7. **Every commit leaves lock files behind.** Deletes are off by default in connected folders, so git couldn't remove `.git/HEAD.lock`, `objects/maintenance.lock` or its `tmp_obj_*` files. A stale `HEAD.lock` would block Joe's next commit on the Mac. Workaround: ask for delete permission for the folder, which is one prompt, then clean up after each commit. The permission didn't survive a worker restart, so it was asked for twice.

7a. **A permission prompt stalls the thread invisibly.** The thread stopped twice to wait on a delete-permission prompt, at 17:38 and 19:12. Nothing appeared in the thread itself. Joe only found out because the coordinator posted a pointer in the project chat. Factory impact: any step that can raise a prompt is a hidden human gate. Either grant it up front, or have the loop post "waiting on a permission prompt" wherever Joe looks.

## Approvals and decisions

8. **A relayed approval isn't an approval on the Mac.** This was the biggest finding.
   - What happened: Joe tapped decision cards in the thread, the thread passed the answers to the RC session, and the Mac's auto-mode check blocked `runway go 03` as an unrequested commit.
   - Why: messages from another Claude session don't count as the user's own words, by design. Otherwise prompt injection could approve commits on Joe's Mac.
   - What cleared it: Joe's own typed "go" in the thread. The RC session received that message directly.
   - The rejected options: bypass mode (`--dangerously-skip-permissions`) drops the check for everything. A narrow allow rule for `runway.py` is possible but wasn't added.
   - Factory design consequence: approval must land in the tracker, and Runway reads it on a schedule (see `decisions.md`).
9. **Cards are a good surface.** Joe answered both decisions within about 20 minutes, from the app. The packet content transferred well to a card: options with consequences and a recommendation. The problem was only the route from the card to the Mac.

## Two Claudes in one thread

10. **The thread and the RC session both answer Joe.** Joe's messages reach both. When he asked "still going?", "is that a limitation?" and "what about bypass mode?", the RC session drafted its own answer each time, alongside the thread's. Only the thread posts to Joe, so he saw one answer each time, but the two can disagree. On one point they did: RC suggested adding a permission rule, while the thread was more cautious. Factory impact: give one session the voice and the other the hands.
11. **One stale claim had to be corrected.** The thread told Joe "running them now" before RC had actually run anything. RC then reported the block. The message was struck through and corrected. Lesson: don't report device work as started until the device confirms it.

## Platform stability

12. **Worker restarts and tool reconnects.** The thread's worker restarted twice mid-task. The MCP servers (folder tools, remote control) disconnected and reconnected several times, and their tools vanished from the list in between. Nothing was lost, because state lived in files and git. Factory impact: keep all loop state on disk, as Runway does, never in a session's memory.
13. **Timestamps are mixed.** Runway logs local Mac time (EDT), while the project reports UTC, so 15:33 in `runway.log` is 19:33 in the thread. Runway should log timezone-aware timestamps.

## What worked smoothly

- RC started on the pre-approved folder with no approval card.
- The coordinator relayed Joe's project-chat question ("do we even need a SoftwareFactory?") into this thread with his own words attached, so no context was lost.
- pm's credential-guard hook fired inside the RC session as designed. Hooks keep working under Runway.
- The first real run needed no config changes. `--allowedTools` and the read-only prep command worked first try.
