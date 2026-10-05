#!/usr/bin/env python3
"""A tiny in-memory stand-in for Linear's GraphQL API, enough for Runway's adapter.

Serves the exact queries in linear_tracker.py, so the Linear path can be tested offline.
POST /graphql as usual; POST /seed with a JSON list of issues; POST /comment to add a
comment as Joe; GET /dump to see the state.
"""
import json, sys, itertools
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "01-runway"))
import linear_tracker as lt

ids = itertools.count(1)
STATES = [{"id": "s-backlog", "name": "Backlog", "type": "backlog", "position": 0},
          {"id": "s-todo", "name": "Todo", "type": "unstarted", "position": 1},
          {"id": "s-prog", "name": "In Progress", "type": "started", "position": 2},
          {"id": "s-done", "name": "Done", "type": "completed", "position": 3},
          {"id": "s-cancel", "name": "Canceled", "type": "canceled", "position": 4}]
TEAM = {"id": "team-1", "key": "SF", "name": "SoftwareFactory"}
LABELS = {}  # name -> id
ISSUES = {}  # id -> dict
NOW = itertools.count(0)


def ts():
    return f"2026-10-05T20:{next(NOW) // 60:02d}:{next(NOW) % 60:02d}.000Z"


def node(i):
    blockers = [ISSUES[b] for b in i["blocked_by"]]
    st = next(s for s in STATES if s["id"] == i["state"])
    return {"id": i["id"], "identifier": i["identifier"], "number": i["number"], "title": i["title"],
            "description": i["description"], "url": f"https://linear.app/fake/issue/{i['identifier']}",
            "state": {"id": st["id"], "name": st["name"], "type": st["type"]},
            "labels": {"nodes": [{"id": LABELS[n], "name": n} for n in i["labels"]]},
            "comments": {"nodes": i["comments"]},
            "inverseRelations": {"nodes": [{"type": "blocks", "issue": {
                "identifier": b["identifier"], "number": b["number"], "title": b["title"],
                "state": {"type": next(s for s in STATES if s["id"] == b["state"])["type"]}}} for b in blockers]}}


def handle(q, v):
    if q == lt.Q_ISSUES:
        proj = v["filter"].get("project", {}).get("name", {}).get("eq")
        ns = [node(i) for i in ISSUES.values() if not proj or i["project"] == proj]
        return {"issues": {"nodes": ns, "pageInfo": {"hasNextPage": False, "endCursor": None}}}
    if q == lt.Q_ISSUE:
        return {"issue": node(ISSUES[v["id"]])}
    if q == lt.Q_TEAM:
        return {"teams": {"nodes": [dict(TEAM, states={"nodes": STATES},
                                         labels={"nodes": [{"id": i, "name": n} for n, i in LABELS.items()]})]},
                "issueLabels": {"nodes": []}}
    if q == lt.Q_PROJECTS:
        return {"projects": {"nodes": [{"id": "p1", "name": v["name"]}]}}
    if q == lt.M_LABEL:
        n = v["input"]["name"]; LABELS[n] = f"l-{n}"
        return {"issueLabelCreate": {"success": True, "issueLabel": {"id": LABELS[n], "name": n}}}
    if q == lt.M_UPDATE:
        i, inp = ISSUES[v["id"]], v["input"]
        if "stateId" in inp: i["state"] = inp["stateId"]
        names = {lid: n for n, lid in LABELS.items()}
        for lid in inp.get("addedLabelIds", []):
            if names[lid] not in i["labels"]: i["labels"].append(names[lid])
        for lid in inp.get("removedLabelIds", []):
            i["labels"].remove(names[lid])
        return {"issueUpdate": {"success": True}}
    if q == lt.M_COMMENT:
        ISSUES[v["input"]["issueId"]]["comments"].append({"body": v["input"]["body"], "createdAt": ts()})
        return {"commentCreate": {"success": True}}
    raise ValueError("unknown query")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        self.reply({k: {**v, "state": next(s["name"] for s in STATES if s["id"] == v["state"])} for k, v in ISSUES.items()})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/seed":
            for n, t in enumerate(body, 1):
                for l in t.get("labels", []): LABELS.setdefault(l, f"l-{l}")
                iid = f"i{n}"
                ISSUES[iid] = {"id": iid, "identifier": f"SF-{n}", "number": n, "title": t["title"],
                               "description": t.get("description", ""), "project": t.get("project", "Practice"),
                               "state": "s-todo", "labels": list(t.get("labels", [])), "comments": [],
                               "blocked_by": [f"i{b}" for b in t.get("blocked_by", [])]}
            return self.reply({"ok": True})
        if self.path == "/comment":
            ISSUES[body["id"]]["comments"].append({"body": body["body"], "createdAt": ts()})
            return self.reply({"ok": True})
        if self.headers.get("Authorization") != "test-key":
            return self.reply({"errors": [{"message": "auth"}]}, 401)
        try:
            self.reply({"data": handle(body["query"], body.get("variables") or {})})
        except Exception as e:
            self.reply({"errors": [{"message": repr(e)}]})

    def reply(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8765), H).serve_forever()
