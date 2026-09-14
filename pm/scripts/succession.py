#!/usr/bin/env python3
"""Durable, single-chain session succession. Host operations belong to the skill."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    p = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    require(p.returncode == 0, p.stderr.strip() or 'Git command failed')
    return p.stdout.strip() if '-z' not in args else p.stdout


def local_file(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'reference must name an existing project file')
    return path


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_directory(root):
    return Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve() / 'pm-succession'


def runtime_file(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(runtime_directory(root)) and path.is_file(),
            'briefs and receipts must be files in the reported runtime_dir')
    return path


def binding(root, relative, identity, closed=False):
    path = local_file(root, relative)
    require(path.parent == (root / '_pm/sessions').resolve(), 'session must be directly under _pm/sessions')
    content = path.read_text()
    require(re.findall(r'^Session-ID: (.+)$', content, re.M) == [identity], 'session identity mismatch')
    require(bool(re.search(r'^Closed: .+$', content, re.M)) == closed,
            'predecessor session must be closed' if closed else 'successor/current session must be open')
    return {'path': str(path.relative_to(root)), 'id': identity}


def policy(root, relative):
    path = local_file(root, relative)
    data = json.loads(path.read_text())
    keys = {'policy', 'approved', 'scope', 'max_sessions', 'allow_create_successor', 'authorization_ref'}
    require(isinstance(data, dict) and set(data) == keys, 'succession policy has missing or unknown fields')
    require(data['policy'] == 'dc-succession-beta-v1', 'unknown succession policy')
    require(data['approved'] is True and data['allow_create_successor'] is True,
            'explicit approved succession opt-in and creation authorization required')
    require(type(data['max_sessions']) is int and data['max_sessions'] >= 1, 'max_sessions must be positive')
    require(isinstance(data['scope'], str) and data['scope'].strip(), 'scope must be nonempty')
    require(isinstance(data['authorization_ref'], str), 'authorization_ref must be a project file')
    authority = local_file(root, data['authorization_ref'])
    return {**data, 'path': str(path.relative_to(root)), 'sha256': fingerprint(path),
            'authorization_sha256': fingerprint(authority)}


def authorization(root, state):
    saved = state['policy']
    require(policy(root, saved['path']) == saved,
            'authorization or policy changed; stop and reconcile the chain before continuing')


def ready(root, brief, allowed=()):
    require(git(root, 'rev-parse', 'HEAD') == brief['revision'], 'checkout revision changed since handoff')
    dirty = set(filter(None, git(root, 'diff', '--name-only', '-z', 'HEAD').split('\0')))
    dirty.update(filter(None, git(root, 'diff', '--cached', '--name-only', '-z', 'HEAD').split('\0')))
    dirty.update(filter(None, git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')))
    require(not dirty - set(allowed), 'checkout contains unfinished changes; reconcile before succession')


def read_brief(root, relative):
    text = runtime_file(root, relative).read_text()
    require(len(text) <= 12000, 'handoff must be compact (at most 12000 characters); link to evidence')
    brief = json.loads(text)
    strings = {'ticket', 'revision', 'summary', 'next_step'}
    lists = {'decisions', 'verification', 'blockers'}
    require(isinstance(brief, dict) and set(brief) == strings | lists, 'handoff has missing or unknown fields')
    for key in strings:
        require(isinstance(brief[key], str) and brief[key].strip(), f'{key} must be nonempty text')
    for key in lists:
        require(isinstance(brief[key], list) and all(isinstance(v, str) and v.strip() for v in brief[key]),
                f'{key} must be a list of nonempty strings')
    require(brief['verification'], 'handoff needs verification references')
    ready(root, brief)
    return brief


def atomic_write(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.succession-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2); f.write('\n')
            f.flush(); os.fsync(f.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def store(root):
    require(Path(git(root, 'rev-parse', '--show-toplevel')).resolve() == root,
            'root must be the project checkout root')
    directory = runtime_directory(root)
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / 'state.json'
        data = json.loads(path.read_text()) if path.exists() else None
        if data:
            require(data.get('version') == 1, 'unsupported succession state version')
            require(data['root'] == str(root), 'chain belongs to another checkout; use its recorded root')
        yield path, data


def transition(state, phase, actor):
    state['phase'] = phase
    state['updated'] = now()
    state['events'].append({'phase': phase, 'actor': actor, 'at': state['updated']})


def evidence(root, relative):
    text = runtime_file(root, relative).read_text().strip()
    require(0 < len(text) <= 12000, 'evidence must be nonempty and at most 12000 characters')
    return {'path': relative, 'text': text, 'at': now()}


def current_actor(state, actor):
    require(state['current']['host_session'] == actor, 'only the recorded predecessor may perform this action')


def attempt_matches(state, attempt):
    require((state.get('handoff') or {}).get('attempt') == attempt, 'launch attempt mismatch')


def update(root, state, args):
    command = args.command
    require(state is not None, 'no chain; explicitly opt in with start first')
    if command == 'status':
        require(not args.chain or state['chain_id'] == args.chain, 'chain identity mismatch')
        return state
    require(state['chain_id'] == args.chain, 'chain identity mismatch')
    if command not in {'stop', 'not-created', 'retire', 'created', 'cancel'}:
        authorization(root, state)
    if command in {'prepare', 'launch', 'created', 'not-created', 'retire', 'stop', 'cancel'}:
        current_actor(state, args.actor)
    phase = state['phase']
    handoff = state.get('handoff')
    if command == 'prepare':
        require(phase == 'active', 'prepare requires an active chain')
        require(state['sessions_started'] < state['policy']['max_sessions'], 'beta session budget reached; close and stop')
        binding(root, state['current']['path'], state['current']['id'], closed=True)
        brief = read_brief(root, args.brief_file)
        state['handoff'] = {'brief': brief, 'prepared': now(), 'failed_attempts': []}
        transition(state, 'prepared', args.actor)
    elif command == 'launch':
        require(phase in {'prepared', 'launching', 'created', 'acknowledged'}, 'no prepared handoff to launch')
        if phase == 'prepared':
            ready(root, handoff['brief'])
            handoff['attempt'] = str(uuid.uuid4())
            transition(state, 'launching', args.actor)
    elif command == 'created':
        attempt_matches(state, args.attempt)
        require(phase in {'launching', 'created', 'acknowledged', 'retired'}, 'creation receipt is out of order')
        require(args.successor != args.actor, 'successor must be a fresh host session')
        require(not handoff.get('successor_host_session') or handoff['successor_host_session'] == args.successor,
                'conflicting successor identity; reconcile without spawning again')
        handoff['successor_host_session'] = args.successor
        if phase == 'launching':
            transition(state, 'created', args.actor)
    elif command == 'acknowledge':
        attempt_matches(state, args.attempt)
        require(phase in {'launching', 'created', 'acknowledged'}, 'acknowledgement is out of order')
        require(args.actor != state['current']['host_session'], 'successor must be a fresh host session')
        require(not handoff.get('successor_host_session') or handoff['successor_host_session'] == args.actor,
                'successor host identity mismatch')
        successor = {**binding(root, args.session, args.id), 'host_session': args.actor}
        require(successor['id'] != state['current']['id'], 'successor needs its own session record')
        require(not handoff.get('successor') or handoff['successor'] == successor, 'successor session identity mismatch')
        ready(root, handoff['brief'], [successor['path']])
        handoff['successor_host_session'] = args.actor
        handoff['successor'] = successor
        if phase != 'acknowledged':
            transition(state, 'acknowledged', args.actor)
    elif command == 'retire':
        require(phase in {'acknowledged', 'retired'}, 'retirement requires successor acknowledgement')
        if phase != 'retired':
            binding(root, state['current']['path'], state['current']['id'], closed=True)
            handoff['resource_release'] = evidence(root, args.evidence_file)
            transition(state, 'retired', args.actor)
    elif command == 'begin':
        if phase == 'active':
            current_actor(state, args.actor)
            return state
        require(phase == 'retired' and handoff['successor']['host_session'] == args.actor,
                'successor must wait for predecessor retirement')
        successor = handoff['successor']
        binding(root, successor['path'], successor['id'])
        ready(root, handoff['brief'], [successor['path']])
        state['history'].append({**handoff, 'predecessor': state['current'], 'began': now()})
        state['current'] = successor
        state['sessions_started'] += 1
        state['handoff'] = None
        transition(state, 'active', args.actor)
    elif command == 'not-created':
        attempt_matches(state, args.attempt)
        require(phase == 'launching', 'absence can only reconcile an uncertain launch')
        handoff['failed_attempts'].append({'attempt': args.attempt, 'absence': evidence(root, args.evidence_file)})
        del handoff['attempt']
        transition(state, 'prepared', args.actor)
    elif command == 'cancel':
        attempt_matches(state, args.attempt)
        require(phase in {'launching', 'created', 'acknowledged', 'retired'},
                'cancellation requires a pending successor')
        handoff['cancellation'] = evidence(root, args.evidence_file)
        state['stop_reason'] = 'Successor cancelled; host absence/stoppage recorded in handoff.'
        transition(state, 'stopped', args.actor)
    elif command == 'stop':
        require(phase in {'active', 'prepared', 'stopped'}, 'reconcile pending successor before stopping')
        if phase != 'stopped':
            require(args.reason.strip(), 'stop reason is required')
            binding(root, state['current']['path'], state['current']['id'], closed=True)
            state['stop_reason'] = args.reason
            transition(state, 'stopped', args.actor)
    return state


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', default='.')
    sub = ap.add_subparsers(dest='command', required=True)
    boundary = sub.add_parser('boundary', help='Use actual context occupancy, never cumulative usage')
    boundary.add_argument('--tickets-completed', type=int, required=True)
    boundary.add_argument('--context-tokens', type=int)
    boundary.add_argument('--safe-boundary', action='store_true')
    sub.add_parser('status').add_argument('--chain')
    start = sub.add_parser('start')
    start.add_argument('--policy-file', required=True)
    start.add_argument('--host', choices=['claude', 'codex'], required=True)
    for name in ['start', 'prepare', 'launch', 'created', 'acknowledge', 'retire', 'begin', 'not-created', 'stop', 'cancel']:
        p = start if name == 'start' else sub.add_parser(name)
        p.add_argument('--actor', required=True, help='Actual host session ID, not the PM session UUID')
        if name != 'start': p.add_argument('--chain', required=True)
        if name in {'start', 'acknowledge'}:
            p.add_argument('--session', required=True); p.add_argument('--id', required=True)
        if name in {'created', 'acknowledge', 'not-created', 'cancel'}: p.add_argument('--attempt', required=True)
        if name in {'retire', 'not-created', 'cancel'}: p.add_argument('--evidence-file', required=True)
        if name == 'prepare': p.add_argument('--brief-file', required=True)
        if name == 'created': p.add_argument('--successor', required=True)
        if name == 'stop': p.add_argument('--reason', required=True)
    return ap


def main():
    args = parser().parse_args()
    try:
        for name in ('actor', 'successor', 'attempt', 'id'):
            value = getattr(args, name, None)
            require(value is None or bool(value.strip()), f'{name} must be nonempty')
        if args.command == 'boundary':
            require(args.tickets_completed >= 0 and (args.context_tokens is None or args.context_tokens >= 0),
                    'counts must be nonnegative')
            rotate = args.tickets_completed >= 2 or (args.context_tokens is not None and args.context_tokens >= 150000)
            result = {'decision': ('rotate' if args.safe_boundary else 'checkpoint') if rotate else 'continue',
                      'source': 'ticket-fallback' if args.context_tokens is None else 'context-occupancy',
                      'context_tokens': args.context_tokens, 'tickets_completed': args.tickets_completed}
        else:
            root = Path(args.root).resolve()
            with store(root) as (path, state):
                before = json.dumps(state, sort_keys=True)
                if args.command == 'start':
                    selected = policy(root, args.policy_file)
                    current = {**binding(root, args.session, args.id), 'host_session': args.actor}
                    if state and state['phase'] != 'stopped':
                        require(state['current'] == current and state['policy'] == selected and state['host'] == args.host,
                                'another chain is already active; recover it instead of starting another')
                    else:
                        if state:
                            atomic_write(path.with_name(state['chain_id'] + '.json'), state)
                        state = {'version': 1, 'chain_id': str(uuid.uuid4()), 'root': str(root), 'host': args.host,
                                 'policy': selected, 'current': current, 'sessions_started': 1,
                                 'history': [], 'handoff': None, 'events': [], 'started': now()}
                        transition(state, 'active', args.actor)
                    result = state
                else:
                    dispatch = args.command == 'launch' and state is not None and state['phase'] == 'prepared'
                    result = update(root, state, args)
                    if args.command == 'launch':
                        result = {**result, 'dispatch_allowed': dispatch}
                if args.command != 'status' and before != json.dumps(state, sort_keys=True):
                    atomic_write(path, state)
                result = {**result, 'state_path': str(path), 'runtime_dir': str(path.parent)}
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
