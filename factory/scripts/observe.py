#!/usr/bin/env python3
"""Read-only Runway observer. Writes only its own dedup state and event packets.

No agent calls, process inspection, tracker calls, credentials, or runner actions.
Use --once for a snapshot, otherwise check every 600 seconds. Events do not wake AI.
"""
import argparse
import datetime
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import time
from pathlib import Path

MAX_PACKETS = 1000
MAX_QUEUE_BYTES = 2 * 1024 * 1024
LOG_BYTES = 256 * 1024
LOG_BACKUPS = 2


def atomic_write(path, text):
    temp = path.with_suffix('.tmp')
    with temp.open('wb' if isinstance(text, bytes) else 'w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def retained(packets):
    result, size, ids = [], 0, set()
    for packet in reversed(packets[-MAX_PACKETS:]):
        if packet.get('id') in ids:
            continue
        ids.add(packet.get('id'))
        length = len((json.dumps(packet) + '\n').encode())
        if size + length > MAX_QUEUE_BYTES:
            break
        result.append(packet)
        size += length
    return list(reversed(result))


def service_logger(out, max_bytes=LOG_BYTES):
    logger = logging.Logger('runway-observer', level=logging.INFO)
    for name, level in [('service.log', logging.INFO), ('service-error.log', logging.ERROR)]:
        # Bound pre-upgrade outputs immediately, including error logs that may
        # receive no new messages. Touch only the exact observer-owned filenames.
        for suffix in ['', *[f'.{n}' for n in range(1, LOG_BACKUPS + 1)]]:
            path = out / (name + suffix)
            if path.exists() and path.stat().st_size > max_bytes:
                with path.open('rb') as stream:
                    stream.seek(-max_bytes, os.SEEK_END)
                    tail = stream.read(max_bytes)
                atomic_write(path, tail.split(b'\n', 1)[-1])
        handler = RotatingFileHandler(out / name, maxBytes=max_bytes,
                                      backupCount=LOG_BACKUPS, encoding='utf-8')
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    return logger


def read_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def inspect(root, saved):
    pm = root / '_pm'
    events = []
    heartbeat = read_json(pm / 'runway-state.json')
    if heartbeat.get('phase') in ('waiting', 'stopped', 'paused'):
        event = {'kind': 'attention', 'phase': heartbeat['phase'],
                       'ticket': heartbeat.get('ticket'),
                       'reason': str(heartbeat.get('reason', ''))[:500],
                       'since': heartbeat.get('since')}
        signature = {k: v for k, v in event.items() if k != 'since'}
        if signature != saved.get('attention'):
            events.append(event)
        saved['attention'] = signature
    else:
        saved['attention'] = None
    # Consume only appended complete records. Retain a partial line for the next pass.
    path = pm / 'runway-runs.jsonl'
    offset = saved.get('offset', 0)
    identity = saved.get('identity')
    try:
        with path.open('rb') as stream:
            st = os.fstat(stream.fileno())
            if 'baseline_end' not in saved:
                saved['baseline_identity'] = st.st_ino
                saved['baseline_end'] = st.st_size if 'offset' not in saved else 0
            if identity != st.st_ino or st.st_size < offset:
                offset = 0
            stream.seek(offset)
            for _ in range(500):
                start = stream.tell()
                line = stream.readline(65537)
                if len(line) > 65536:
                    offset = stream.tell()  # discard oversized fragments without blocking the queue
                    continue
                if not line or not line.endswith(b'\n'):
                    break
                offset = stream.tell()
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(row, dict):
                    continue
                kind = row.get('kind')
                if kind in ('finish', 'prep') or (kind == 'outcome' and row.get('result') not in ('done', 'stopped')) or row.get('exit', 0) != 0:
                    event = {k: row[k] for k in ('at', 'kind', 'ticket', 'result', 'exit', 'check_exit', 'pr') if k in row}
                    event['_baseline'] = st.st_ino == saved['baseline_identity'] and start < saved['baseline_end']
                    events.append(event)
            saved['identity'] = st.st_ino
            saved['offset'] = offset
    except OSError:
        pass
    # Age can flag a review need, but cannot establish that a process is dead.
    if heartbeat.get('phase') in ('agent', 'check', 'prep', 'merge', 'sync', 'finish'):
        config = read_json(root / 'runway.json')
        try:
            since = datetime.datetime.fromisoformat(heartbeat['since']).timestamp()
            budget = int(config.get('agent_timeout_s', 3600))
            # Finish includes panel, fix, checks and PR generation, each with a budget.
            multiplier = 6 if heartbeat['phase'] == 'finish' else 1
            if time.time() - since > budget * multiplier + 120:
                events.append({'kind': 'overdue', 'phase': heartbeat['phase'],
                               'ticket': heartbeat.get('ticket'), 'since': heartbeat['since'],
                               'reason': 'Phase exceeds time budget; verify liveness before acting.'})
        except (KeyError, ValueError, TypeError):
            pass
    return events, heartbeat


def tick(root, out):
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / 'state.json'
    saved = read_json(state_path)
    # State and packets are one atomic commit. JSONL is a bounded projection,
    # rebuilt even when the previous export failed after the state committed.
    packets = saved.get('packets')
    if packets is None:
        packets = []
        legacy = out / 'events.jsonl'
        if legacy.exists():
            with legacy.open() as stream:
                for line in stream:
                    try:
                        packet = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(packet, dict):
                        packets = retained(packets + [packet])
    history = list(dict.fromkeys(saved.get('seen', []) + [p['id'] for p in packets if isinstance(p.get('id'), str)]))
    seen = set(history)
    baseline = 'offset' not in saved
    events, heartbeat = inspect(root, saved)
    emitted = []
    context = None
    for event in events:
        historical = event.pop('_baseline', baseline)
        key = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        history.append(key)
        if context is None:
            config = read_json(root / 'runway.json')
            branch = config.get('integration_branch', 'runway/integration')
            try:
                result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify',
                                         'refs/heads/' + str(branch)], capture_output=True,
                                        text=True, timeout=5)
                head = result.stdout.strip() if result.returncode == 0 else None
            except (OSError, subprocess.SubprocessError):
                head = None
            context = {'observed_integration_head': head,
                       'check_command': str(config.get('check_cmd', ''))[:500]}
        packet = {'id': key, 'observed_at': time.time(), 'repo': str(root),
                  'event': {k: v[:500] if isinstance(v, str) else v for k, v in event.items()},
                  'baseline': historical, 'liveness': 'unverified', **context}
        # Local publication draft only: no logs, credentials or tracker calls.
        packet['issue_draft'] = {'related_ticket': event.get('ticket'),
                                'candidate_head': context['observed_integration_head'],
                                'command': context['check_command'],
                                'error_excerpt': None, 'publishing_enabled': False,
                                'note': 'Observed head may differ from the historical event head; verify before publishing.'}
        packets.append(packet)
        emitted.append(packet)
    saved['seen'] = history[-2000:]
    saved['snapshot'] = {k: heartbeat.get(k) for k in ('phase', 'ticket', 'attempt', 'since', 'pid', 'agent_pid')}
    saved['checked_at'] = time.time()
    saved['last_check_seconds'] = time.perf_counter() - started
    saved['packets'] = retained(packets)
    atomic_write(state_path, json.dumps(saved, indent=2) + '\n')
    atomic_write(out / 'events.jsonl', ''.join(json.dumps(p) + '\n' for p in saved['packets']))
    return emitted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--interval', type=int, default=600, choices=range(30, 3601), metavar='SECONDS')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out or root / '_pm' / 'observer'
    # One observer per output directory; never acquire the runner's lock.
    import fcntl
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'observer.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        logger = service_logger(out)
        while True:
            try:
                packets = tick(root, out)
                logger.info('Check complete; %d new events', len(packets))
                if args.once:
                    for packet in packets:
                        print(json.dumps(packet), flush=True)
            except Exception as error:
                logger.error('%s: %s', type(error).__name__, str(error)[:1000])
                if args.once:
                    raise
            if args.once:
                return
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
