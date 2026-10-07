# Sandcastle

> Checked against the [GitHub README](https://github.com/mattpocock/sandcastle) on 2026-10-05. Re-check before relying on it.

## What it is

Matt Pocock's MIT-licensed TypeScript library for running coding agents in sandboxes. It's the execution engine of his factory: a script calls `run()`, the agent loops inside a container until it signals done, and the result comes back as commits on a branch. It has no scheduler and no approval gates. You bring the triggers, and you put human checks in hooks or in your own script.

```bash
npm install --save-dev @ai-hero/sandcastle
npx @ai-hero/sandcastle init      # scaffolds .sandcastle/ (Dockerfile, prompt.md, .env)
npx tsx .sandcastle/main.ts
```

## Verified details

- **Agents:** `claudeCode()`, `codex()`, `pi()`, `cursor()`, `opencode()`, `copilot()`.
- **Sandboxes:** `docker()`, `podman()`, `vercel()`, `noSandbox()`, or custom providers (bind-mount or isolated).
- **Branch strategies:** `head` (default, writes to your working dir), `merge-to-head` (temp branch merged back), or a named `branch` (persistent, for PRs).
- **Loop end:** `<promise>COMPLETE</promise>` (configurable), `maxIterations` (default 1), or a 600s idle timeout.
- **Prompt files** support `{{PLACEHOLDERS}}` and `` !`command` `` blocks that run inside the sandbox. That's how an agent pulls its own work, e.g. `` !`gh issue list --label ready-for-agent` ``.
- **Structured output** via Zod schemas, plus session resume and fork for Claude Code, Codex and Pi.
- **Templates:** `blank`, `simple-loop`, `sequential-reviewer`, `parallel-planner`, `parallel-planner-with-review`.

## The open auth question, answered

The notes marked "how Claude Code authenticates in the container" as unverified. The README says credentials go in `.sandcastle/.env` and are injected at runtime:

- **Subscription (Max):** `CLAUDE_CODE_OAUTH_TOKEN`, generated with `claude setup-token`.
- **API:** `ANTHROPIC_API_KEY`.

**(unverified)** Whether running unattended loops on a subscription token stays within Anthropic's usage terms and plan limits for this kind of automation. Check the current terms before running parallel loops on the Max plan.

## Where it fits for Joe

| Fit | Notes |
|---|---|
| Good | Git-native, script-driven and readable, which matches the "script manager" decision. Templates map onto Runway's lanes: `sequential-reviewer` is the AFK lane with a review step. |
| Good | Docker gives real isolation on the Mac mini: an agent can't touch other projects or credentials outside the mount. |
| Weak | No scheduler, gates or lookahead. The judgment lane still has to be built around it, which is what Runway does. |
| Weak | Docker on a 16 GB machine limits parallel containers (pm's own ceiling is three sessions). |
| Not a fit | FileMaker work (binary files, no text diffs). Keep it to the TypeScript and Python repos. |

## Recommendation

Don't start with it. Run experiment 01 with headless `claude -p` on the host first, to test the loop shape without Docker or token setup. If the shape works, experiment 02 swaps Runway's `agent_cmd` for a small `sandcastle-run.ts` that calls `run({ agent: claudeCode(...), sandbox: docker(), branchStrategy: { type: "branch", branch } })` (option shape from memory, check the README). The tracker, gates and lookahead stay the same.
