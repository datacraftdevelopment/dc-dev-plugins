#!/usr/bin/env python3
"""Render the current work list of a pm-scaffolded repo as one HTML page.

Reads   docs/intent/inbox.md, docs/intent/*.md, .scratch/*/issues/*.md
Writes  <repo>/_pm/board.html  -- always that one file, always overwritten.

No dependencies, no model, no history. Run it whenever you want to look.

usage: board.py [repo-root]      (default: current directory)
"""
import html
import re
import sys
from datetime import datetime
from pathlib import Path

DONE = {"resolved", "done", "closed", "shipped"}
ACTIVE = {"claimed", "in-progress", "in progress", "active"}
ORDER = {"human": 0, "active": 1, "ready": 2, "blocked": 3, "done": 4}
STATE = {"human": "needs human", "active": "in progress", "ready": "ready", "blocked": "blocked", "done": "done"}


# ---------- read ----------

def first_heading(text):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def header_line(text, key):
    m = re.search(rf"^{key}:\s*(.*)$", text, re.M | re.I)
    return m.group(1).strip() if m else ""


def unmark(s):
    """Strip bold and turn [text](link) into text."""
    return re.sub(r"\*\*|\[([^\]]+)\]\([^)]+\)", r"\1", s)


def read_inbox(root):
    f = root / "docs/intent/inbox.md"
    if not f.exists():
        return []
    items = []
    for line in f.read_text().splitlines():
        m = re.match(r"^-\s+(\d{4}-\d{2}-\d{2})\s*[·•-]\s*([^·•]+?)\s*[·•]\s*(.+)$", line)
        if m:
            items.append({"date": m.group(1), "source": m.group(2).strip(), "ask": m.group(3).strip()})
        elif line.startswith("- "):
            items.append({"date": "", "source": "", "ask": line[2:].strip()})
    return items


def read_intents(root):
    d = root / "docs/intent"
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.md")):
        if f.name.lower() in ("inbox.md", "readme.md"):
            continue
        t = f.read_text()
        title = re.sub(r"^Intent:\s*", "", first_heading(t), flags=re.I)
        m = re.search(r"\*\*Status:\*\*\s*([\w-]+)", t)
        status = m.group(1) if m else "shaped"
        m = re.search(r"\*\*Size:\*\*\s*([^·\n]+)", t)
        size = m.group(1).strip() if m else ""
        out.append({"title": title or f.stem, "status": status, "size": size, "path": f})
    return out


def read_efforts(root):
    d = root / ".scratch"
    efforts = []
    if not d.exists():
        return efforts
    for e in sorted(p for p in d.iterdir() if p.is_dir()):
        issues_dir = e / "issues"
        if not issues_dir.exists():
            continue
        dest = ""
        for name in ("map.md", "spec.md"):
            f = e / name
            if f.exists():
                m = re.search(r"^##\s+Destination\s*\n+(.+?)(?:\n\s*\n|\Z)", f.read_text(), re.S | re.M)
                if m:
                    dest = unmark(re.sub(r"\s+", " ", m.group(1))).strip()
                break
        tickets = []
        for f in sorted(issues_dir.glob("*.md")):
            t = f.read_text()
            num = re.match(r"(\d+)", f.name)
            num = num.group(1) if num else ""
            title = re.sub(rf"^{num}\s+", "", first_heading(t)) if num else first_heading(t)
            blocked = header_line(t, "Blocked by")
            blocked_ids = re.findall(r"\b(\d{2})\b", blocked) if blocked.lower() not in ("", "none") else []
            waiting = header_line(t, "Waiting on") or header_line(t, "Waits on")
            if re.match(r"^nothing\b", waiting, re.I):
                waiting = ""
            tickets.append({
                "num": num, "title": title or f.stem, "path": f,
                "type": header_line(t, "Type").lower(),
                "status": header_line(t, "Status").lower() or "open",
                "blocked_ids": blocked_ids, "waiting": unmark(waiting),
            })
        done = {t["num"] for t in tickets if t["status"] in DONE}
        for t in tickets:
            t["open_blockers"] = [b for b in t["blocked_ids"] if b not in done]
        efforts.append({"name": e.name, "dest": dest, "tickets": tickets})
    return efforts


def state_of(t):
    s = t["status"]
    if s in DONE:
        return "done"
    if s == "needs-human" or t["waiting"]:
        return "human"
    if s in ACTIVE:
        return "active"
    if t["open_blockers"]:
        return "blocked"
    return "ready"


# ---------- render ----------

CSS = """
:root{--bg:#F4ECE0;--ink:#2D241B;--muted:#8B7B68;--accent:#C04D2E;--rule:#D9CFC0;--ok:#4F7A5A;--warn:#B8860B}
*{box-sizing:border-box}
body{margin:0 auto;max-width:70ch;padding:0 2rem;background:var(--bg);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,sans-serif}
a{color:inherit;text-decoration:none}a:hover{color:var(--accent)}
header{padding:3rem 0 1.5rem}
.eyebrow{font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem}
h1{font-family:Charter,Georgia,serif;font-size:2.2rem;line-height:1.1;margin:0 0 .5rem}
.meta{color:var(--muted);font-size:.9rem}.meta b{color:var(--ink);font-weight:600}
section{border-top:1px solid var(--rule);padding:1.75rem 0}
section h2{font-family:Charter,Georgia,serif;font-size:1.35rem;margin:0 0 .25rem;display:flex;justify-content:space-between;align-items:baseline}
section h2 .n{font-size:.8rem;color:var(--muted);font-family:ui-sans-serif,system-ui,sans-serif;font-weight:400}
.dest{font-size:.8rem;color:var(--muted);margin:0 0 1rem;font-style:italic}
.empty{color:var(--muted);font-style:italic;font-size:.85rem}
.row{display:grid;grid-template-columns:2.2rem 1fr auto;gap:.6rem;align-items:baseline;padding:.45rem 0;border-bottom:1px dotted var(--rule)}
.row:last-child{border-bottom:0}
.num{color:var(--muted);font-family:ui-monospace,Menlo,monospace;font-size:.78rem}
.t{font-family:Charter,Georgia,serif;font-size:1rem}
.kind{font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-left:.5rem}
.state{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;color:var(--muted)}
.state.ready{color:var(--ok)}.state.blocked,.state.human{color:var(--accent)}.state.active{color:var(--warn)}
.row.done{opacity:.55}
.why{grid-column:2;font-size:.8rem;color:var(--muted);margin-top:-.2rem}
footer{padding:1.5rem 0 3rem;border-top:1px solid var(--rule);color:var(--muted);font-size:.85rem}
"""


def esc(s):
    return html.escape(str(s))


def link(path, root, text):
    return f'<a href="file://{esc(path.resolve())}" title="{esc(path.relative_to(root))}">{text}</a>'


def render(root, inbox, intents, efforts):
    n_tickets = sum(len(e["tickets"]) for e in efforts)
    n_open = sum(1 for e in efforts for t in e["tickets"] if state_of(t) != "done")
    out = [f"<!DOCTYPE html><html lang=en><head><meta charset=utf-8><title>Work · {esc(root.name)}</title><style>{CSS}</style></head><body>",
           f'<header><div class="eyebrow">Work list · rendered from files</div><h1>{esc(root.name)}</h1>'
           f'<p class="meta"><b>{len(inbox)}</b> in inbox · <b>{len(intents)}</b> intents · <b>{n_open}</b> open of <b>{n_tickets}</b> tickets'
           f' · generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</p></header>']

    out.append(f'<section><h2>Inbox <span class="n">{len(inbox)} loose</span></h2>')
    for i in inbox:
        out.append(f'<div class="row"><span class="num">·</span><span class="t">{esc(i["ask"])}</span><span class="state">{esc(i["date"])} · {esc(i["source"])}</span></div>')
    if not inbox:
        out.append('<p class="empty">nothing loose</p>')
    out.append("</section>")

    out.append(f'<section><h2>Intents <span class="n">{len(intents)} shaped</span></h2>')
    for i in intents:
        size = f' · {esc(i["size"])}' if i["size"] else ""
        out.append(f'<div class="row"><span class="num">·</span><span class="t">{link(i["path"], root, esc(i["title"]))}</span><span class="state">{esc(i["status"])}{size}</span></div>')
    if not intents:
        out.append('<p class="empty">none shaped</p>')
    out.append("</section>")

    for e in efforts:
        ts = sorted(e["tickets"], key=lambda t: (ORDER[state_of(t)], t["num"]))
        n_open_e = sum(1 for t in ts if state_of(t) != "done")
        out.append(f'<section><h2>{esc(e["name"])} <span class="n">{n_open_e} open · {len(ts) - n_open_e} done</span></h2>')
        if e["dest"]:
            out.append(f'<p class="dest">{esc(e["dest"])}</p>')
        for t in ts:
            c = state_of(t)
            out.append(f'<div class="row {c}"><span class="num">{esc(t["num"])}</span>'
                       f'<span class="t">{link(t["path"], root, esc(t["title"]))}<span class="kind">{esc(t["type"])}</span></span>'
                       f'<span class="state {c}">{STATE[c]}</span>')
            if c == "blocked":
                out.append(f'<div class="why">blocked by {esc(", ".join(t["open_blockers"]))}</div>')
            elif c == "human" and t["waiting"]:
                out.append(f'<div class="why">waiting on {esc(t["waiting"][:100])}</div>')
            out.append("</div>")
        out.append("</section>")

    out.append("<footer><p>Read-only view. Edit the markdown, rerun, reload. Order within an effort: needs human, in progress, ready, blocked, done.</p></footer></body></html>")
    return "".join(out)


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    page = render(root, read_inbox(root), read_intents(root), read_efforts(root))
    out = root / "_pm" / "board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(out)


if __name__ == "__main__":
    main()
