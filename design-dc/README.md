# design-dc

The DataCraft design plugin — the design half of the Code↔Design loop, packaged.

| Skill | Job |
|---|---|
| `design-handoff` | Write the lean crossing brief for claude.ai/design — specify the unguessable (data model / concepts, flows, vocabulary, rules), delegate every visual decision. Moved here from the pm plugin (≤0.4.0). |
| `html-artifacts` | Rich editorial HTML artifacts instead of long markdown — plans, brainstorms, comparisons, status reports, throwaway editing UIs. Moved here from the pm plugin (≤0.4.0). |
| `design-sync` | Drive the **built-in DesignSync tool** to sync a local component library with a Claude Design *design-system* project — incremental, plan-gated, never wholesale. |

**Boundaries.** Driving the designer itself (send prompts, screenshot the render, pull Prototype-project files) belongs to the **claude-design bridge plugin** — a separate, upstream-tracked fork (`Agentic/Agent/claude-design-mcp`), deliberately not bundled here. The doctrine for when to cross to the designer at all (the vocabulary rule, episodic vs continuous) lives in the library: `wiki/craft/agents/design-loop.md`.

Install (this marketplace):

```
/plugin marketplace add datacraftdevelopment/dc-plugins
/plugin install design-dc@dc-plugins
```
