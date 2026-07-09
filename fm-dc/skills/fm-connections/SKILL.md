---
name: fm-connections
description: Interact with FileMaker databases via Data API and OData. Use when the user wants to query, create, update, or delete records in FileMaker, list tables, check schema, or test connections.
argument-hint: "[command] [table] [options]"
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# FileMaker Database Skill

You are a FileMaker database assistant. Use the CLI tool at `${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py` to interact with FileMaker databases.

## Setup

1. Install dependencies: `pip install -r requirements.txt` (this skill needs `requests`)
2. Credentials come from the **same project-root `.env` the rest of this starter uses** — no extra setup:

```
FM_HOST=https://your-server.fmphost.com
FM_DATABASE=YourDatabase
FM_USERNAME=api_user
FM_PASSWORD=api_password
```

The script finds `.env` by walking up from the working directory. TLS verification is on by default; set `FM_SSL_VERIFY=false` only for dev servers with self-signed certificates.

To talk to additional databases, add named profiles and pass `--profile`:
```
FM_PRODUCTION_SERVER=prod-server.fmphost.com   # bare hostname, no scheme
FM_PRODUCTION_DATABASE=ProdDB
FM_PRODUCTION_USERNAME=api_user
FM_PRODUCTION_PASSWORD=secret
```

Then use `--profile production` to connect (profile vars win over the bare `FM_*` set).

## Available Commands

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py <command> [options]
```

### Connection & Discovery
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py test                          # Test connection
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py tables                        # List all tables
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py schema <table>                # Get table fields
```

### Querying Records
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py query <table>                 # All records
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py query <table> --limit 10      # Limit results
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py query <table> --filter "Name eq 'John'"  # OData filter
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py query <table> --orderby "Name asc"       # Sort
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py query <table> --skip 20 --limit 10       # Pagination
```

### Single Record
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py get <table> <recordID>        # Get by recordID
```

### Create Record (uses Data API for ID safety)
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py create <table> --data '{"FieldName": "value"}'
```

### Update Record (uses Data API with simple recordID)
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py update <table> <recordID> --data '{"FieldName": "new value"}'
```

### Delete Record
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py delete <table> <recordID>
```

### Find (convenience)
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py find <table> <field> <value>              # Exact match
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py find <table> <field> <value> --op contains  # Contains
```

### Count Records
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py count <table>                 # Count all records
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py count <table> --filter "..."  # Count with filter
```

### Switching Databases
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py --database OtherDB --server HOST query TABLE
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fm-connections/scripts/fm.py --profile production query TABLE  # Use named profile
```

## Critical Rules

1. **IDs as strings**: FileMaker uses 57-digit UUID integers. ALWAYS convert to strings when creating/updating records with foreign keys. The CLI handles this automatically.

2. **Auto-managed fields**: NEVER include `CreationAccount`, `ModifyAccount`, `CreationTimestamp`, `ModifyTimestamp` in create/update data. FileMaker sets these automatically. The CLI strips these automatically with a warning.

3. **Hybrid API**: The CLI uses OData for queries (fast) and Data API for creates/updates (reliable with large IDs).

4. **Two ID systems**:
   - `recordID`: Simple sequential ("1", "305") - used for Data API CRUD operations (get, update, delete)
   - `ID`: 57-digit UUID - used for foreign keys (must be string!)

## Known Server Quirks

Some FileMaker OData implementations have quirks. Common ones:

1. **`$select` may not work**: Some servers reject `$select`. If so, query all fields and filter the output yourself.
2. **`$count` may return 0**: Use `query` without `--limit` and count the results via `meta.count`.
3. **Table names**: Layout/table names are case-sensitive. Run `tables` first if unsure.

## Interpreting User Requests

When the user says `$ARGUMENTS`:

- If it looks like a command (e.g., "query USER"), run it directly
- If it's a question (e.g., "show me all active users"), translate to the right query
- If it's vague (e.g., "check FileMaker"), test connection and list tables
- If they want to create/update, confirm the data before executing
- When presenting results, summarize the data in a readable table format rather than dumping raw JSON

## Error Handling

- **Auth failure (401)**: Check `.env` credentials, do NOT retry
- **Not found (404)**: Table/layout name may be wrong — run `tables` to verify
- **"syntax error in URL"**: Likely a `$select` or `$count` issue — drop that parameter and retry
- **Timeout**: Retry once, then suggest adding `--limit`
- **Large ID precision**: The CLI auto-converts, but warn if user passes raw integers

## References

- `references/four-mode-doctrine.md` — when to use ProofKit MCP vs Data API vs OData vs the schema pipeline; layout-as-security-boundary rules. **Read this first when a task involves choosing a connection path.**
- `references/filemaker_integration_guide.md` — all three FM server APIs (Data API, OttoFMS, OData): auth, protocol detail, configuration.
- `references/filemaker_api_reference.md` — Data API endpoint reference.
- `scripts/fm_client.py` — portable zero-dependency Data API client class (login/query/CRUD/logout with session hygiene); use it from generated Python when the CLI (`scripts/fm.py`) is too coarse.
