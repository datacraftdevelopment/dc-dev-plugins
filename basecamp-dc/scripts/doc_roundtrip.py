#!/usr/bin/env python3
"""Quirk-safe round trip for a Basecamp Doc body (the *What shipped* prepend).

Why this exists (quirks 2026-09-10): the API returns every <bc-attachment> with its
rendered <figure><img><figcaption> inside. Send that back unchanged and Basecamp keeps
the attachment AND re-emits the inner figure as a loose <figure>; every save adds a
set. Empty each attachment before sending and drop any loose top-level <figure>.

Usage:
  doc_roundtrip.py clean  < body.html  > clean.html
  doc_roundtrip.py prepend --entry entry.html  < body.html  > new.html
  doc_roundtrip.py check  < body.html          # exit 1 if any <figure> sits outside a <bc-attachment>

Typical flow (ids from .basecamp/config.json → docs.what_shipped; fetch fresh
with `api get` — the show commands can serve a stale cached copy):
  basecamp api get /buckets/<project>/documents/<doc>.json --jq '.content' > body.html
  doc_roundtrip.py prepend --entry entry.html < body.html > new.html   # stop first if body.html is empty
  doc_roundtrip.py check < new.html
  basecamp files update <doc> --title "What shipped" --content "$(cat new.html)" --json
  basecamp api get /buckets/<project>/documents/<doc>.json --jq '.content'   # verify the entry landed
"""
import argparse, re, sys

ATTACH = re.compile(r"(<bc-attachment\b[^>]*>).*?(</bc-attachment>)", re.S)
LOOSE_FIGURE = re.compile(r"<figure\b(?![^>]*bc-attachment)[^>]*>.*?</figure>", re.S)


def clean(html):
    html = ATTACH.sub(r"\1\2", html)
    # after emptying attachments, any <figure> left is a stray copy
    return LOOSE_FIGURE.sub("", html)


def counts(html):
    """(loose figures, attachments). A figure inside a <bc-attachment> is Basecamp's own
    rendering and fine; one outside is a duplicate left by an earlier raw round trip."""
    loose = ATTACH.sub(r"\1\2", html).count("<figure")
    return loose, html.count("<bc-attachment")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("clean", "prepend", "check"))
    ap.add_argument("--entry", help="HTML/Markdown-rendered entry to put at the top (prepend)")
    a = ap.parse_args()
    body = sys.stdin.read()
    if a.cmd == "check":
        loose, att = counts(body)
        ok = loose == 0
        print(f"loose_figures={loose} attachments={att} {'OK' if ok else 'DUPLICATES — run clean'}", file=sys.stderr)
        return 0 if ok else 1
    out = clean(body)
    if a.cmd == "prepend":
        if not a.entry:
            print("prepend needs --entry <file>", file=sys.stderr)
            return 2
        with open(a.entry) as f:
            out = f.read().rstrip() + "\n" + out
    loose, att = counts(out)
    if loose:
        print(f"doc_roundtrip: {loose} loose <figure> left after clean ({att} attachments); refusing to emit", file=sys.stderr)
        return 1
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
