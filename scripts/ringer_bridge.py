#!/usr/bin/env python3
"""Run the existing Ringer clone without copying its engine, config, or secrets."""
import os
import json
from pathlib import Path
import sys


def ringer_root():
    configured = os.environ.get('RINGER_ROOT')
    root = Path(configured).expanduser() if configured else Path.home() / 'Agentic-Mini/_Core/Ringer'
    root = root.resolve()
    if not (root / 'ringer.py').is_file():
        raise SystemExit('Ringer not found. Set RINGER_ROOT to the existing clone containing ringer.py.')
    return root


if __name__ == '__main__':
    root = ringer_root()
    if sys.argv[1:] == ['--print-root']:
        print(root)
    elif sys.argv[1:] == ['--grill-template']:
        manifest = json.loads((root / 'local/templates/grill-review/manifest.template.json').read_text())
        if len(manifest.get('tasks', [])) != 1:
            raise SystemExit('Expected one reviewer in the shared grill template; inspect the updated kit.')
        task = manifest['tasks'][0]
        task['engine'] = 'claude'
        task['model'] = 'claude-fable-5'
        task['key'] = 'round-{{ROUND}}-fable'
        task.pop('engine_args', None)  # Codex reasoning flags do not belong to the Claude worker.
        print(json.dumps(manifest, indent=2))
    else:
        os.execv(sys.executable, [sys.executable, str(root / 'ringer.py'), *sys.argv[1:]])
