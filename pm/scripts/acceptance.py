#!/usr/bin/env python3
"""Validate an acceptance evidence record, not the truth of its evidence.

The evaluator runs checks; this helper catches missing, conflicting, or
self-reported entries. It neither deploys nor marks an intent complete.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def verdict(record):
    criteria = record.get('criteria')
    if not isinstance(criteria, dict) or not criteria or not all(criteria.values()): return 'blocked'
    if not record.get('candidate') or not record.get('implementer') or not record.get('intent'): return 'blocked'
    exceptions_used = False
    for phase in ('local', 'delivery'):
        data = record.get(phase)
        if phase == 'delivery' and data is None:
            return 'blocked' if exceptions_used else 'ready-for-release'
        if not isinstance(data, dict): return 'blocked'
        if data.get('revision') != record['candidate'] or not data.get('environment'): return 'blocked'
        if phase == 'delivery' and not data.get('applied_by'): return 'blocked'
        checks = data.get('checks', [])
        if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks): return 'blocked'
        ids = [c.get('id') for c in checks]
        if len(ids) != len(set(ids)) or set(ids) != set(criteria): return 'blocked'
        for check in checks:
            if not all(check.get(f) for f in ('evaluator', 'evidence', 'at')): return 'blocked'
            if check['evaluator'] == record['implementer']: return 'blocked'
            if check.get('status') == 'pass': continue
            if check.get('status') not in ('fail', 'not-run'): return 'blocked'
            exception = next((e for e in record.get('exceptions', [])
                              if e.get('id') == check['id'] and e.get('phase') == phase), None)
            if not exception or not all(exception.get(k) for k in ('approved_by','reason','at')): return 'blocked'
            exceptions_used = True
    return 'released-with-exceptions' if exceptions_used else 'shipped'


def intent_criteria(text):
    section = re.search(r'^## Acceptance\s*$\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not section: return {}
    result = {}
    entries = re.findall(r'^- \[[ xX]\] (.+)$', section[1], re.M)
    # The supported intent format is a checkbox line per observable criterion.
    for n, entry in enumerate(entries, 1):
        match = re.match(r'(A[0-9]+): (.+)$', entry)
        key, value = (match[1], match[2]) if match else (f'A{n}', entry)
        if key in result: raise ValueError('duplicate acceptance ID in intent')
        result[key] = value
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--record', required=True)
    ap.add_argument('--intent', required=True, help='actual accepted intent file; digest must match the record')
    args = ap.parse_args()
    try:
        record = json.loads(Path(args.record).read_text())
        actual = hashlib.sha256(Path(args.intent).read_bytes()).hexdigest()
        if record.get('intent_sha256') != actual:
            print(json.dumps({'status':'blocked','reason':'intent changed or digest missing'})); return 2
        expected = intent_criteria(Path(args.intent).read_text())
        if not expected or expected != record.get('criteria'):
            print(json.dumps({'status':'blocked','reason':'record criteria differ from accepted intent'})); return 2
        status = verdict(record)
        print(json.dumps({'status':status, 'record':args.record,
                          'verified':'record completeness and revision/identity consistency; not evidence authenticity or deployment'}))
        return 2 if status == 'blocked' else 0
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)})); return 2


if __name__ == '__main__':
    sys.exit(main())
