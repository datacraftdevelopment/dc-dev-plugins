#!/usr/bin/env python3
"""Export/check PM's policy snapshot in an explicitly selected build-swarm source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-swarm', required=True)
    ap.add_argument('--check', action='store_true', help='verify byte parity without writing')
    args = ap.parse_args()
    source = ROOT / 'pm/scripts/credential-policy.json'
    target = Path(args.build_swarm).expanduser().resolve() / 'scripts/credential-policy.json'
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if args.check:
        if not target.is_file() or target.read_bytes() != raw:
            print('FAIL: PM/build-swarm credential policies differ; export and retest both consumers.'); return 1
        print('PASS: credential policy byte parity, SHA-256 '+digest); return 0
    if not target.parent.is_dir():
        print('FAIL: target must be an existing build-swarm source with scripts/'); return 1
    target.write_bytes(raw)
    revision = subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    target.with_suffix('.provenance.json').write_text(json.dumps({
        'source':'dc-plugins/pm/scripts/credential-policy.json', 'source_base_revision':revision,
        'sha256':digest,'note':'Content identity is the digest; source base revision may precede uncommitted policy edits.'},indent=2)+'\n')
    print('Exported credential policy snapshot: '+str(target)); return 0


if __name__ == '__main__':
    sys.exit(main())
