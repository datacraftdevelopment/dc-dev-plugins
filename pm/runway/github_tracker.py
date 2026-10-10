"""GitHub Issues adapter for Runway: reads the queue, and claims, finishes, parks and releases issues.

Runway's queue is the issues in one repo that carry Matt Pocock's triage labels, the same ones the
Linear adapter reads:

  ready-for-agent   AFK work. Runway runs it.                      (Gate: auto)
  ready-for-human   Needs Joe. Runway preps a packet first.         (Gate: human)
  go                Joe's approval on a ready-for-human issue.      (Gate: approved)
  needs-human       Parked: waiting on Joe. Runway never picks it.  (Status: needs-human)
  spec              A spec (what /to-spec publishes). Never run, even with a Runway label.
  harness:<name>    Per-issue harness override.

An issue with sub-issues is a spec too, label or not: its sub-issues are the tickets. A spec has gate
`none`, so Runway never runs it, but it still gates a ticket that names it as a blocker. The first
time a labelled spec is skipped, one line goes to `_pm/runway.log`.

Config: `"tracker": "github"`, and the repo from `"github": {"repo": "owner/name"}`, else from the
clone's `origin` remote. Optional `"github": {"gh": "<gh command>"}` (default `gh`).

Writes (through `gh issue edit / comment / close`; every comment starts with the 🛫 runway marker):

  claim    assign the gh user (`@me`), comment `Claimed-by: <machine> · Started on <branch>`
  resolve  close as completed, the note as the closing comment
  park     add `needs-human`, remove the assignee, comment why. Removing the label makes it ready again
  release  (pause --stop-now, signed out) remove the assignee and comment; the claim clears

Decisions (ready-for-human issues):

  post_packet  comment the decision packet (🛫 marker) and add `needs-human`
  approve      comment `Approved. <note>` first (the durable record), then add `go` (if not there) and remove
               `needs-human`. A label write that fails is finished by the next sync, from that comment
  decline      `drop` closes as not planned; anything else is a comment, the issue stays parked
  sync         for each parked issue: the `go` label, or Joe's latest comment since Runway last wrote
               starting `go` (the rest of that comment is the note) approves; starting `drop` declines.
               Only a trusted author's comment counts (OWNER, MEMBER, COLLABORATOR). A stranger's go or
               drop is ignored and logged once in `_pm/runway.log`. Runway's own 🛫 comments are never Joe's.

Status: closed (completed or not planned) is resolved; open with `needs-human` is needs-human; open with
an assignee is claimed; anything else is ready.

Blockers: GitHub's native issue dependencies ("blocked by"); when an issue has none, a
`Blocked by: #n, #m` line at the top of its body. A blocker without Runway's labels still gates, as a
stub issue Runway never runs (like Linear's out-of-project blockers). Ids are `#n` (`owner/name#n` for
another repo).

Ticket text is the body plus comments from trusted authors only (author association OWNER, MEMBER or
COLLABORATOR). Other comments are left out and a one-line note says how many. Runway's own 🛫 marker
comments (packet, claimed_by) are read from trusted comments only, so a stranger can't forge a claim.

Cost of one `load()`, in `gh` calls: ceil(N / 50) + 1 at most, where N is the number of open and closed
issues carrying a Runway label (one GraphQL page of 50 issues each, labels, assignee count, the last 50
comments and native blockers included), plus one call only when some issue names a blocker in its body
that isn't already loaded. Nothing else is fetched. `reload()` is one call.

Every `gh` call is cut off after `github.timeout_s` (default 60). A timeout, a connection reset or a 5xx is
retried twice, then the tick ends cleanly (see transient.py). A comment or close that timed out is looked up
before it is repeated, so it is never posted twice; a close is looked up for the close itself, and when only
its comment landed the repeat closes without it.

Auth: `gh` must be installed and signed in (`gh auth login`, or GH_TOKEN in the environment). Anything
else is one clear error naming both, not a traceback.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ticket_protocol  # noqa: E402
import transient  # noqa: E402

TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
PAGE = 50
DEFAULTS = {
    "repo": "",
    "gh": "gh",
    "timeout_s": 60,
    "agent_label": "ready-for-agent",
    "human_label": "ready-for-human",
    "approve_label": "go",
    "needs_human_label": "needs-human",
    "spec_label": "spec",
}
AUTH_HELP = "GitHub CLI isn't ready. Install gh and run `gh auth login`, or set GH_TOKEN."
AUTH_RE = re.compile(r"gh auth login|GH_TOKEN|GITHUB_TOKEN|not logged in|authentication|bad credentials|HTTP 401",
                     re.I)

# What gh prints when GitHub or the network hiccups (retried), as opposed to a real refusal.
TRANSIENT_RE = re.compile(r"timed? ?out|timeout|connection (reset|refused|closed|aborted)|HTTP 5\d\d|HTTP 429|"
                          r"\b50[0234]\b|bad gateway|service unavailable|gateway time|unexpected EOF|\bEOF\b|"
                          r"no such host|could not resolve host|network is unreachable|TLS handshake|rate limit|"
                          r"temporarily unavailable", re.I)

COMMENT_FIELDS = "body createdAt authorAssociation author { login }"
ISSUE_FIELDS = """
  number title body url state stateReason
  labels(first: 30) { nodes { name } }
  assignees(first: 10) { totalCount nodes { login } }
  comments(last: 50) { pageInfo { hasPreviousPage startCursor } nodes { %s } }
  subIssues { totalCount }
  blockedBy(first: 25) { nodes { number title state repository { nameWithOwner } } }
""" % COMMENT_FIELDS

# Matt Pocock's five triage labels; `runway setup` creates any that are missing (his skills expect them).
MATT_LABELS = [
    ("needs-triage", "FBCA04", "Maintainer needs to evaluate this issue"),
    ("needs-info", "D4C5F9", "Waiting on reporter for more information"),
    ("ready-for-agent", "4EA7FC", "Fully specified, ready for an AFK agent"),
    ("ready-for-human", "F2994A", "Needs a human"),
    ("wontfix", "FFFFFF", "Will not be actioned"),
]

Q_ISSUES ="""query($owner: String!, $name: String!, $labels: [String!], $after: String) {
  repository(owner: $owner, name: $name) {
    issues(first: %d, after: $after, labels: $labels, states: [OPEN, CLOSED],
           orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes { %s }
      pageInfo { hasNextPage endCursor }
    }
  }
}""" % (PAGE, ISSUE_FIELDS)

Q_OLDER = """query($owner: String!, $name: String!, $number: Int!, $before: String!) {
  repository(owner: $owner, name: $name) { issue(number: $number) {
    comments(last: %d, before: $before) { pageInfo { hasPreviousPage startCursor } nodes { %s } }
  } }
}""" % (PAGE, COMMENT_FIELDS)

Q_ONE = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { issue(number: $number) { %s } }
}""" % ISSUE_FIELDS


def repo_from_origin(root: Path) -> str:
    r = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True)
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", r.stdout.strip())
    if r.returncode != 0 or not m:
        sys.exit('No GitHub repo: set "github": {"repo": "owner/name"} in runway.json '
                 "(this clone has no github.com origin).")
    return f"{m.group(1)}/{m.group(2)}"


class GitHub:
    def __init__(self, cfg: dict):
        self.cmd = shlex.split(cfg["gh"])
        self.timeout = float(cfg.get("timeout_s") or 60)

    def run(self, args, landed=None) -> str:
        """One gh call, cut off after `timeout_s`. A timeout, a reset or a 5xx is retried (transient.py),
        then raises TrackerDown. landed: for a write that isn't safe to repeat, a check that it is there.
        args may be a function, called for each attempt, when what to repeat depends on what `landed` found."""
        build = args if callable(args) else (lambda: args)

        def once() -> str:
            try:
                r = subprocess.run(self.cmd + build(), capture_output=True, text=True, timeout=self.timeout)
            except FileNotFoundError:
                sys.exit(AUTH_HELP)
            if r.returncode != 0:
                out = r.stderr + r.stdout
                if AUTH_RE.search(out):
                    sys.exit(AUTH_HELP)
                if TRANSIENT_RE.search(out):
                    raise transient.TransientError(f"gh failed: {out.strip()[:200]}")
                raise RuntimeError(f"gh failed: {out.strip()[:500]}")
            return r.stdout
        out = transient.retry(once, "gh " + " ".join(build()[:2]), landed)
        return out or ""

    def graphql(self, query: str, **variables) -> dict:
        args = ["api", "graphql", "-f", f"query={query}"]
        for k, v in variables.items():
            if v is None:
                continue
            if isinstance(v, list):
                for item in v:
                    args += ["-f", f"{k}[]={item}"]
            elif isinstance(v, int):
                args += ["-F", f"{k}={v}"]
            else:
                args += ["-f", f"{k}={v}"]
        stdout = self.run(args)
        try:
            out = json.loads(stdout)
        except ValueError:
            raise RuntimeError(f"gh returned something that isn't JSON: {stdout[:200]}") from None
        if out.get("errors"):
            raise RuntimeError(f"GitHub API error: {out['errors']}")
        return out["data"]


def _blockers_from_body(body: str) -> list[int]:
    """`Blocked by: #n, #m` as the first non-blank line of the body."""
    for line in (body or "").splitlines():
        if line.strip():
            m = re.match(r"\s*blocked by:\s*(.+)$", line, re.I)
            return [int(n) for n in re.findall(r"#(\d+)", m.group(1))] if m else []
    return []


class GitHubTicket(ticket_protocol.Ticket):
    """An issue as GitHub tells it. Facts and writes only: the rules are in ticket_protocol."""
    rules = ticket_protocol.GITHUB
    effort = "github"

    @property
    def pr_ref(self) -> str:
        return f"Refs {self.id}"  # "#12": GitHub links it itself

    def __init__(self, node: dict, tracker: "GitHubTracker"):
        self.node = node
        number = node["number"]
        comments = [self._fact(c) for c in node["comments"]["nodes"]]
        self._back = (node["comments"].get("pageInfo") or {})  # where the next older page starts
        super().__init__(tracker, id=f"#{number}", num=f"#{number}", title=node["title"], url=node.get("url"),
                         body=node.get("body"), labels={l["name"] for l in node["labels"]["nodes"]},
                         comments=comments, slug_head=f"gh-{number}")  # the engine matches blockers by num

    @staticmethod
    def _fact(c: dict) -> dict:
        return {"body": c["body"], "createdAt": c["createdAt"],
                "trusted": c.get("authorAssociation") in TRUSTED,
                "who": (c.get("author") or {}).get("login") or "unknown",
                "assoc": c.get("authorAssociation", "NONE")}

    def _older_comments(self) -> list[dict]:
        """The next 50 comments back from what has been read (one call), oldest first; [] at the start of history."""
        if not self._back.get("hasPreviousPage"):
            return []
        d = self.tr.api.graphql(Q_OLDER, owner=self.tr.owner, name=self.tr.name,
                                number=int(self.num.rsplit("#", 1)[1]),
                                before=self._back["startCursor"])["repository"]["issue"]["comments"]
        self._back = d["pageInfo"]
        return [self._fact(c) for c in d["nodes"]]

    # -- facts --

    @property
    def closed(self) -> bool:
        return self.node["state"] == "CLOSED"  # completed or not planned

    @property
    def held(self) -> bool:
        return self.node["assignees"]["totalCount"] > 0

    @property
    def has_children(self) -> bool:
        return (self.node.get("subIssues") or {}).get("totalCount", 0) > 0

    @property
    def blocked_by(self) -> list[str]:
        native = [self.tr.ref(b["repository"]["nameWithOwner"], b["number"])
                  for b in self.node["blockedBy"]["nodes"]]
        if native:
            return native
        return [self.tr.ref(self.tr.repo, n) for n in _blockers_from_body(self.node.get("body") or "")]

    # -- writes --

    def _issue(self, verb: str, *args: str, landed=None) -> None:
        self.tr.api.run(["issue", verb, self.num[1:], "--repo", self.tr.repo, *args], landed=landed)

    def _landed(self, full: str):
        """A check that a comment written from now on is already on the issue (for a write that timed out)."""
        since = transient.since_mark()

        def check() -> bool:
            node = self.tr.fetch(self)
            return transient.posted_since(node["comments"]["nodes"], full, since)
        return check

    def _post(self, full: str) -> None:
        self._issue("comment", "--body", full, landed=self._landed(full))

    def _unassign(self) -> list[str]:
        """Args that drop whoever holds the issue (the gh user when the node doesn't say)."""
        who = [a["login"] for a in self.node["assignees"].get("nodes", [])] or ["@me"]
        return ["--remove-assignee", ",".join(who)]

    def _claim(self) -> None:
        self._issue("edit", "--add-assignee", "@me")

    def _close(self, reason: str, full: str | None) -> None:
        """gh posts the comment, then closes, so a timeout can leave the comment on an open issue. A repeat then
        closes without the comment; a close that did happen is not repeated."""
        since = transient.since_mark()
        commented = [False]

        def landed() -> bool:
            node = self.tr.fetch(self)
            if node["state"] == "CLOSED":
                return True
            commented[0] = transient.posted_since(node["comments"]["nodes"], full, since)
            return False

        def args() -> list[str]:
            tail = [] if commented[0] else ["--comment", full]
            return ["issue", "close", self.num[1:], "--repo", self.tr.repo, "--reason", reason, *tail]
        self.tr.api.run(args, landed=landed)

    def _label_args(self, add, remove) -> list[str]:
        args = []
        for name in add:
            args += ["--add-label", name]
        for name in remove:
            if name in self.labels:
                args += ["--remove-label", name]
        return args

    def _release(self, add=(), remove=()) -> None:
        self._issue("edit", *self._label_args(add, remove), *self._unassign())

    def _relabel(self, add=(), remove=()) -> None:
        args = self._label_args(add, remove)
        if args:
            self._issue("edit", *args)


class GitHubTracker(ticket_protocol.Tracker):
    rules = ticket_protocol.GITHUB

    @staticmethod
    def signins(cfg: dict) -> list:
        return ["gh"]

    def __init__(self, root: Path, cfg: dict):
        self.root = root
        self.c = dict(DEFAULTS, **cfg.get("github", {}))
        self.repo = self.c["repo"] or repo_from_origin(root)
        if not re.fullmatch(r"[^/\s]+/[^/\s]+", self.repo):
            sys.exit(f'github.repo must look like "owner/name", got {self.repo!r}.')
        self.owner, self.name = self.repo.split("/")
        self.api = GitHub(self.c)

    def setup(self) -> None:
        """Check gh auth, the repo and Issues, create Runway's missing labels, warn when the repo is public."""
        self.api.run(["auth", "status"])
        try:
            info = json.loads(self.api.run(["repo", "view", self.repo, "--json", "hasIssuesEnabled,isPrivate"]))
        except RuntimeError as e:
            sys.exit(f"Can't see {self.repo} with this gh sign-in: {e}")
        print(f"Repo: {self.repo} ({'private' if info['isPrivate'] else 'PUBLIC'})")
        if not info["hasIssuesEnabled"]:
            sys.exit(f"Issues is turned off on {self.repo}. Turn it on (Settings, Features, Issues), then run setup again.")
        have = {x["name"].lower() for x in json.loads(self.api.run(
            ["label", "list", "--repo", self.repo, "--limit", "200", "--json", "name,color"]))}
        wanted = {"agent_label": ("4EA7FC", "Runway: AFK build work"),
                  "human_label": ("F2994A", "Runway: needs Joe's call first"),
                  "approve_label": ("4CB782", "Runway: Joe approved a ready-for-human issue"),
                  "needs_human_label": ("EB5757", "Runway: parked, waiting on Joe"),
                  "spec_label": ("8B8FA3", "A spec: its sub-issues are the tickets. Runway never runs it")}
        todo = [(self.c[key], color, desc) for key, (color, desc) in wanted.items()]
        todo += [(n, c, d) for n, c, d in MATT_LABELS if n not in {t[0] for t in todo}]  # Matt's five, for his skills
        for name, color, desc in todo:
            if name.lower() in have:
                print(f"Label {name}: exists")
                continue
            self.api.run(["label", "create", name, "--repo", self.repo, "--color", color, "--description", desc])
            print(f"Label {name}: created")
        if not info["isPrivate"]:
            print(f"WARNING: {self.repo} is PUBLIC. Its issues and comments are public too: no client names, "
                  "credentials or NDA material in issues, and Runway's decision packets and comments are readable by anyone.")

    def ref(self, repo: str, number: int) -> str:
        return f"#{number}" if repo.lower() == self.repo.lower() else f"{repo}#{number}"

    def _create(self, title: str, full: str, labels: list[str]) -> str:
        """Open a new issue in the repo and return its ref ("#12"). `full` is the marked body. A create that
        timed out is looked up before it is repeated."""
        since = transient.since_mark()
        found: list[int] = []

        def landed() -> bool:
            rows = json.loads(self.api.run(["issue", "list", "--repo", self.repo, "--state", "all", "--limit", "30",
                                            "--json", "number,title,body,createdAt"]))
            for r in rows:
                if r["title"] == title and r["body"] == full and transient.posted_since([r], full, since, key="body"):
                    found.append(r["number"])
                    return True
            return False
        args = ["issue", "create", "--repo", self.repo, "--title", title, "--body", full]
        for name in labels:
            args += ["--label", name]
        out = self.api.run(args, landed=landed)
        m = re.search(r"/issues/(\d+)", out)
        number = int(m.group(1)) if m else (found[0] if found else None)
        if number is None:
            raise RuntimeError(f"gh created an issue but printed no URL: {out[:200]}")
        return self.ref(self.repo, number)

    # -- the tracker interface Runway uses --

    def load(self) -> list[GitHubTicket]:
        labels = [self.c["agent_label"], self.c["human_label"]]
        nodes, after = [], None
        while True:
            d = self.api.graphql(Q_ISSUES, owner=self.owner, name=self.name, labels=labels,
                                 after=after)["repository"]["issues"]
            nodes += d["nodes"]
            if not d["pageInfo"]["hasNextPage"]:
                break
            after = d["pageInfo"]["endCursor"]
        tickets = [GitHubTicket(n, self) for n in sorted(nodes, key=lambda n: n["number"])]
        self._log_spec_skips(tickets)
        known = {t.id for t in tickets}
        stubs: dict[str, dict] = {}
        for t in tickets:
            for b in t.node["blockedBy"]["nodes"]:
                bid = self.ref(b["repository"]["nameWithOwner"], b["number"])
                if bid not in known and bid not in stubs:
                    stubs[bid] = {"number": b["number"], "title": b["title"], "state": b["state"]}
        # Body-line blockers aren't in the payload: one aliased call fetches them all.
        want = sorted({n for t in tickets if not t.node["blockedBy"]["nodes"]
                       for n in _blockers_from_body(t.node.get("body") or "")
                       if self.ref(self.repo, n) not in known | set(stubs)})
        if want:
            q = "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { %s } }" % " ".join(
                f"i{n}: issue(number: {n}) {{ number title state }}" for n in want)
            found = self.api.graphql(q, owner=self.owner, name=self.name)["repository"]
            for n in want:
                got = found.get(f"i{n}") or {"number": n, "title": f"#{n}", "state": "OPEN"}  # unknown still gates
                stubs[self.ref(self.repo, n)] = got
        for bid, b in stubs.items():
            tickets.append(GitHubTicket({
                "number": b["number"], "title": b["title"], "body": "", "url": "", "state": b["state"],
                "stateReason": None, "labels": {"nodes": []}, "assignees": {"totalCount": 0},
                "comments": {"nodes": []}, "blockedBy": {"nodes": []},
            }, self))
            tickets[-1].id = tickets[-1].num = bid
        return tickets

    def fetch(self, t: GitHubTicket) -> dict:
        d = self.api.graphql(Q_ONE, owner=self.owner, name=self.name, number=int(t.num.rsplit('#', 1)[1]))
        return d["repository"]["issue"]

    def reload(self, t: GitHubTicket) -> GitHubTicket:
        return GitHubTicket(self.fetch(t), self)
