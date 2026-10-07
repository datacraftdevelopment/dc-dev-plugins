# DataCraft Software Factory site

A static presentation site for the DataCraft agentic software workflow: Hermes
for persistent project management, DataCraft PM plugin for orchestration, Ringer for
verified delegation and receipts, and the CLI worker lanes underneath it.

The front page is a compact field-guide index. Focused pages cover the AI-native
SDLC, system architecture, operating loop, evidence and receipts, model/CLI
routing, and the live Hermes experiment. The plugin catalog at `dist/plugins/`
links to pages for PM, Ringer, UI testing, design, FileMaker, standards, and the
Basecamp client face. Hermes also has its own system page.

## Preview locally

```bash
python3 -m http.server 4173 --directory dist
```

Then open <http://127.0.0.1:4173>.

The site has no build step or runtime dependencies.
