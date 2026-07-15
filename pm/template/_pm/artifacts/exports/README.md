# Exports

Exports from systems you're integrating with or replacing. Schemas, screenshots, configuration dumps.

## What goes here

- FileMaker DDR XML (if the project touches FM — typically `exports/ddr/YYYY-MM-DD/`)
- Database schemas (SQL dumps, Prisma schemas, JSON Schema)
- Screenshots of existing UI
- API documentation exports from existing systems
- Postman collections or similar

## Why exports, not raw `schema/` or `data/`

The scaffold is codebase-agnostic — `exports/` is a neutral home for whatever you exported. If the engagement grows a code surface with its own structured pipeline (e.g. an fm-dc-scaffolded FileMaker setup with DDR parsing, or an `_app/` with schema tooling), that pipeline takes over and this folder becomes "miscellaneous exports."
