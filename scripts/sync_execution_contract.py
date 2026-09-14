#!/usr/bin/env python3
"""Import/check PM's bundled agreement contract from the canonical build-swarm source.

The canonical agreement_contract.py lives beside the build-swarm runtime loader;
PM bundles an exact byte copy at pm/scripts/agreement_contract.py so the installed
plugin never imports across an absolute library path. This script is the only
sanctioned way to move bytes between the two — run with --check in CI/tests to
prove they have not diverged.
"""
import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-swarm', required=True, help='canonical build-swarm skill root (contains scripts/agreement_contract.py)')
    ap.add_argument('--check', action='store_true', help='verify byte parity without writing')
    args = ap.parse_args()
    source = Path(args.build_swarm).expanduser().resolve() / 'scripts/agreement_contract.py'
    target = ROOT / 'pm/scripts/agreement_contract.py'
    if not source.is_file():
        print('FAIL: canonical agreement contract not found: ' + str(source)); return 1
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if args.check:
        if not target.is_file() or target.read_bytes() != raw:
            print('FAIL: PM bundled agreement contract differs from the canonical build-swarm copy; re-export and retest both consumers.'); return 1
        print('PASS: agreement contract byte parity, SHA-256 ' + digest); return 0
    target.write_bytes(raw)
    print('Imported canonical agreement contract: ' + str(target) + ' SHA-256 ' + digest); return 0


if __name__ == '__main__':
    sys.exit(main())
