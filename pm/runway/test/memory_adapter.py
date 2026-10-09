"""An in-memory tracker adapter for tests: facts from a dict, writes into the same dict, and a list of the writes
in the order they happened. Configure it as GitHub or Linear by passing that tracker's `Rules`.

    tr = MemoryTracker(root, ticket_protocol.LINEAR, [issue("DAT-1", labels=["ready-for-human"])])
    t = tr.load()[0]
    t.mark_claimed("b", "Mini-One")
    tr.ops   # [("comment", "🛫 runway · Claimed-by: ..."), ("claim",)]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ticket_protocol  # noqa: E402

LABELS = {"agent_label": "ready-for-agent", "human_label": "ready-for-human", "approve_label": "go",
          "needs_human_label": "needs-human", "spec_label": "spec"}


def issue(id, title="A ticket", body="", url=None, labels=(), comments=(), closed=False, held=False,
          children=False, blocked_by=()):
    """`comments` are (body, trusted) pairs, or (body, trusted, who, assoc[, createdAt]). Oldest first."""
    out = []
    for i, c in enumerate(comments):
        body_, trusted, *rest = c
        who, assoc, at = (rest + ["unknown", "NONE", f"2026-10-{i + 1:02d}T10:00:00Z"][len(rest):])[:3]
        out.append({"body": body_, "createdAt": at, "trusted": trusted,
                    "who": who, "assoc": assoc})
    return {"id": id, "title": title, "body": body, "url": url, "labels": list(labels), "comments": out,
            "closed": closed, "held": held, "children": children, "blocked_by": list(blocked_by)}


class MemoryTicket(ticket_protocol.Ticket):
    effort = "memory"

    def __init__(self, data: dict, tracker: "MemoryTracker"):
        self.rules = tracker.rules
        self.data = data
        every = data["comments"]
        self.held_from = max(0, len(every) - tracker.window) if tracker.window else 0  # the window: latest N
        super().__init__(tracker, id=data["id"], num=data["id"], title=data["title"], url=data["url"],
                         body=data["body"], labels=set(data["labels"]), comments=every[self.held_from:],
                         slug_head=data["id"].lower())

    def _older_comments(self) -> list[dict]:
        """The next page of comments back from the window (a page is the window size), oldest first."""
        if not self.held_from:
            return []
        start = max(0, self.held_from - self.tr.window)
        page, self.held_from = self.data["comments"][start:self.held_from], start
        self.tr.page_backs += 1
        return page

    # -- facts --

    closed = property(lambda self: self.data["closed"])
    held = property(lambda self: self.data["held"])
    has_children = property(lambda self: self.data["children"])
    blocked_by = property(lambda self: list(self.data["blocked_by"]))

    # -- writes --

    def _comment_in(self, full: str) -> None:
        n = len(self.data["comments"]) + 1
        at = self.tr.now or f"2026-10-{n:02d}T10:00:00Z"  # tests set `tr.now` to put writes minutes apart
        self.data["comments"].append({"body": full, "createdAt": at, "trusted": True,
                                      "who": "runway", "assoc": "OWNER"})

    def _change(self, add, remove) -> None:
        labels = self.data["labels"]
        labels[:] = [n for n in labels if n not in remove] + [n for n in add if n not in labels]

    def _post(self, full: str) -> None:
        self.tr.ops.append(("comment", full))
        self._comment_in(full)

    def _claim(self) -> None:
        if self.tr.claim_fails:
            raise RuntimeError("claim transition failed")
        self.tr.ops.append(("claim",))
        self.data["held"] = True

    def _close(self, reason: str, full: str | None) -> None:
        self.tr.ops.append(("close", reason, full))
        self.data["closed"], self.data["held"] = True, False
        if full is not None:
            self._comment_in(full)

    def _release(self, add=(), remove=()) -> None:
        self.tr.ops.append(("release", list(add), list(remove)))
        self.data["held"] = False
        self._change(add, remove)

    def _relabel(self, add=(), remove=()) -> None:
        self.tr.ops.append(("relabel", list(add), list(remove)))
        self._change(add, remove)


class MemoryTracker(ticket_protocol.Tracker):
    def __init__(self, root: Path, rules: ticket_protocol.Rules, issues=()):
        self.root, self.rules, self.c = root, rules, dict(LABELS)
        self.issues = list(issues)
        self.ops: list[tuple] = []
        self.now: str | None = None      # createdAt for the next comment a write posts
        self.window: int | None = None   # a ticket reads only its latest N comments (None: all of them)
        self.page_backs = 0              # how many times a ticket asked for an older page
        self.claim_fails = False         # the claim transition raises, after the stamp has landed

    def load(self) -> list[MemoryTicket]:
        tickets = [MemoryTicket(d, self) for d in self.issues]
        self._log_spec_skips(tickets)
        return tickets

    def reload(self, t: MemoryTicket) -> MemoryTicket:
        return MemoryTicket(t.data, self)

    def _create(self, title: str, full: str, labels: list[str]) -> str:
        self.ops.append(("create", title, full, list(labels)))
        n = len(self.issues) + 1
        self.issues.append(issue(f"MEM-{n}", title=title, body=full, labels=labels))
        return f"MEM-{n}"
