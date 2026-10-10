"""Deterministic acceptance inventory from complete original ticket bodies.

Only explicit Acceptance/Acceptance criteria sections with Markdown bullets are supported.
Ambiguous inventories fail closed rather than asking the judge to invent coverage.
"""
import hashlib
import re


def inventory(tickets):
    rows, errors = [], []
    for t in tickets:
        body = getattr(t, 'body', None)
        body = t.text if body is None else body
        sections = re.findall(r'^#{1,6}\s+Acceptance(?: criteria)?\s*\n(.*?)(?=^#{1,6}\s|\Z)',
                              body, re.I | re.M | re.S)
        if len(sections) != 1:
            errors.append(f'{t.id}: expected one explicit Acceptance section in the complete ticket body')
            continue
        criteria = []
        for line in sections[0].splitlines():
            if not line.strip():
                continue
            m = re.match(r'^\s*[-*+]\s+(?:\[[ xX]\]\s*)?(.+)', line)
            if m:
                criteria.append(m.group(1).strip())
            elif criteria and line[:1].isspace():
                criteria[-1] += ' ' + line.strip()
            else:
                errors.append(f'{t.id}: ambiguous acceptance text: {line.strip()[:100]}')
        if not criteria or len(criteria) != len(set(criteria)):
            errors.append(f'{t.id}: empty or duplicate acceptance criteria')
        for text in criteria:
            cid = hashlib.sha256((t.id+'\n'+text).encode()).hexdigest()[:20]
            rows.append({'ticket': t.id, 'id': cid, 'criterion': text})
    if len({(r["ticket"], r["id"]) for r in rows}) != len(rows):
        errors.append("Duplicate stable criterion identity in expected inventory")
    if not rows:
        errors.append("No complete done-ticket acceptance inventory is available")
    return rows, errors


def coverage(expected, actual):
    errors, seen = [], set()
    known = {(r['ticket'], r['id']): r['criterion'] for r in expected}
    for r in actual:
        key = (r.get('ticket'), r.get('id'))
        if key not in known:
            errors.append(f'Unknown acceptance criterion: {key}')
        elif key in seen:
            errors.append(f'Duplicate acceptance evidence: {key}')
        elif r.get('criterion') != known[key]:
            errors.append(f'Acceptance criterion text changed: {key}')
        elif not r.get('evidence', '').strip():
            errors.append(f'Missing acceptance evidence: {key}')
        seen.add(key)
    errors += [f'Omitted acceptance criterion: {key}' for key in known.keys()-seen]
    return errors
