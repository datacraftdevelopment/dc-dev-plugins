"""Transient tracker failures, shared by the Linear and GitHub adapters (DAT-46).

A timeout, a connection reset or a 5xx from the tracker is retried a couple of times with a short
backoff. If it keeps failing, `retry` raises TrackerDown; Runway's tick catches that, ends cleanly
(log line, heartbeat `waiting`, one notification until it clears) and the next tick tries again.
Auth errors and everything else are not transient: they surface as they always did.

Writes: a write that timed out may already have landed. Pass `landed` (a callable that re-reads the
tracker and answers whether the write is there) and `retry` checks it before every repeat, so a comment
is never posted twice.
"""
from __future__ import annotations

import datetime as dt
import http.client
import os
import subprocess
import time
import urllib.error

TRIES = 3  # the first attempt plus two retries
# Seconds to wait before the 2nd and 3rd attempt. RUNWAY_BACKOFF_S="0,0" turns the wait off (tests).
BACKOFF = tuple(float(x) for x in os.environ.get("RUNWAY_BACKOFF_S", "1,3").split(","))
SLACK_S = 10  # clock skew allowed when matching a comment against the moment a write began


class TransientError(Exception):
    """An adapter's own mark for a failure worth retrying (a gh 502, a Linear 5xx)."""


class TrackerDown(Exception):
    """A tracker call kept failing transiently. `what` names the call; `cause` is the last error."""

    def __init__(self, what: str, cause: BaseException | None = None):
        self.what, self.cause = what, cause
        why = f"{type(cause).__name__}: {cause}" if cause is not None else "no answer"
        super().__init__(f"{what} did not answer ({why[:160]})")


def is_transient(e: BaseException) -> bool:
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code == 429
    return isinstance(e, (TransientError, TimeoutError, ConnectionError, subprocess.TimeoutExpired,
                          urllib.error.URLError, http.client.HTTPException))


def retry(fn, what: str, landed=None):
    """Call fn(); on a transient failure wait and call it again, up to TRIES times, then raise TrackerDown.
    landed: for a write, a callable answering "is it already there?"; it runs before each repeat and
    after the last failure, and a True answer ends the retry as a success (returns None)."""
    last: BaseException | None = None
    for i in range(TRIES):
        if i:
            wait = BACKOFF[min(i - 1, len(BACKOFF) - 1)]
            if wait > 0:
                time.sleep(wait)
            if landed:
                try:
                    if landed():
                        return None
                except Exception as e:  # can't tell whether it landed: don't write again yet
                    if not (isinstance(e, TrackerDown) or is_transient(e)):
                        raise
                    last = e
                    continue
        try:
            return fn()
        except Exception as e:
            if not is_transient(e):
                raise
            last = e
    if landed:
        try:
            if landed():
                return None
        except Exception:
            pass
    raise TrackerDown(what, last)


def since_mark() -> dt.datetime:
    """Taken before a write; `posted_since` later asks whether a comment appeared after it."""
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=SLACK_S)


def posted_since(comments: list[dict], body: str, since: dt.datetime, key: str = "body") -> bool:
    """True when a comment (or, for `key`, any record) with exactly this text was created at or after `since`."""
    for c in comments:
        if c.get(key) != body:
            continue
        try:
            when = dt.datetime.fromisoformat(c["createdAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            return True  # can't date it: assume it's ours rather than post twice
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        if when >= since:
            return True
    return False
