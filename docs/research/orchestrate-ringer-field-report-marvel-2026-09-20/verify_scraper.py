#!/usr/bin/env python3
"""Run from the ROOT of a git worktree of the Marvel repo: python3 verify_scraper.py <catalog|preflight>
Gives the worktree a private COPY of the scraped database and a link to the main checkout's scraper
node_modules, runs the checks for one ticket, then removes both. Never touches the real database."""
import os, re, shutil, sqlite3, subprocess, sys
from pathlib import Path

MAIN = Path("/Users/joe/Agentic-Mini/RPG/Marvel/scraper")
root = Path.cwd()
scraper = root / "scraper"
if not scraper.is_dir():
    sys.exit("verify: run me from the worktree root")
mode = sys.argv[1] if len(sys.argv) > 1 else ""
link, data = scraper / "node_modules", scraper / "data"
made_link = made_data = False
fails = []

def run(cmd, cwd=root):
    done = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return done.returncode, done.stdout

def catalog_files():
    out = {}
    for p in sorted((root / "context/catalog").rglob("*.md")):
        text = p.read_text()
        # the index carries a generated date; ignore it when comparing runs
        out[str(p.relative_to(root))] = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", text)
    return out

try:
    if not link.exists():
        os.symlink(MAIN / "node_modules", link); made_link = True
    if not data.exists():
        data.mkdir(); made_data = True
        shutil.copy(MAIN / "data" / "marvel-rpg.db", data / "marvel-rpg.db")
    db = sqlite3.connect(f"file:{data / 'marvel-rpg.db'}?mode=ro", uri=True)

    if mode == "catalog":
        code, out = run(["node", "scraper/scripts/generate-reference-catalog.js"])
        if code != 0:
            fails.append("generate-reference-catalog.js failed:\n" + "\n".join(out.splitlines()[-25:]))
        else:
            first = catalog_files()
            run(["node", "scraper/scripts/generate-reference-catalog.js"])
            if catalog_files() != first:
                fails.append("running the generator twice gives different output; it must be deterministic")
            index = first.get("context/catalog/00_INDEX.md", "")
            for table in ["maneuvers", "vehicles"]:
                rel = f"context/catalog/{table}.md"
                text = first.get(rel)
                rows = db.execute(f"select name from {table}").fetchall()
                if text is None:
                    fails.append(f"{rel} was not generated"); continue
                entries = re.findall(r"^### .+$", text, re.M)
                if len(entries) != len(rows):
                    fails.append(f"{rel} has {len(entries)} '### ' entries; the {table} table has {len(rows)} rows")
                missing = [n for (n,) in rows if n not in text]
                if missing:
                    fails.append(f"{rel} is missing {len(missing)} names, e.g. {missing[:3]}")
                if re.search(r"</?(p|tooltip|strong|ul|li|h3|span|div)\b", text):
                    fails.append(f"{rel} still contains raw HTML tags; strip them the way the other catalog files do")
                if "Source" not in text:
                    fails.append(f"{rel} never states an entry's source book")
                if f"{table}.md" not in index or str(len(rows)) not in index:
                    fails.append(f"00_INDEX.md does not list {table}.md with its entry count ({len(rows)})")
            vehicles = first.get("context/catalog/vehicles.md", "")
            if vehicles and not re.search(r"Speed", vehicles):
                fails.append("vehicles.md should carry each vehicle's Speed, Powers and Health from element_display")
            code, status = run(["git", "status", "--porcelain", "--", "context/catalog"])
            allowed = {"context/catalog/00_INDEX.md", "context/catalog/maneuvers.md", "context/catalog/vehicles.md"}
            changed = {line[3:].strip() for line in status.splitlines() if line.strip()}
            extra = sorted(changed - allowed)
            if extra:
                fails.append(f"other catalog files changed; only the two new files and the index may: {extra}")
    elif mode == "preflight":
        nvmrc = scraper / ".nvmrc"
        if not nvmrc.exists():
            fails.append("scraper/.nvmrc is missing")
        else:
            want = nvmrc.read_text().strip().lstrip("v").split(".")[0]
            code, have = run(["node", "-v"])
            if want != have.strip().lstrip("v").split(".")[0]:
                fails.append(f".nvmrc pins Node {want}, but the Node that works here is {have.strip()}")
        code, out = run(["node", "scraper/scripts/preflight.js"])
        if code != 0:
            fails.append("node scraper/scripts/preflight.js should exit 0 on this machine:\n" + out[-800:])
        elif "better-sqlite3" not in out:
            fails.append("preflight.js should say it loaded better-sqlite3")
        probe = ("const {backupDb}=require('./scraper/scripts/lib/backup-db.js');"
                 "const p=backupDb(process.argv[1],{now:new Date('2026-09-20T10:11:00Z')});console.log(p);")
        code, out = run(["node", "-e", probe, str(data / "marvel-rpg.db")])
        made = Path(out.strip().splitlines()[-1]) if code == 0 and out.strip() else None
        if code != 0 or not made or not made.exists():
            fails.append("backupDb(dbPath, {now}) from scraper/scripts/lib/backup-db.js should copy the DB and return the new path:\n" + out[-600:])
        else:
            if made.parent.name != "backups" or "2026-09-20" not in made.name:
                fails.append(f"the backup should land in data/backups/ with the date in its name; got {made}")
            if made.stat().st_size != (data / "marvel-rpg.db").stat().st_size:
                fails.append("the backup is not the same size as the database")
            code2, out2 = run(["node", "-e", probe, str(data / "marvel-rpg.db")])
            again = Path(out2.strip().splitlines()[-1]) if code2 == 0 and out2.strip() else None
            if not again or again == made and False:
                fails.append("a second backup the same minute should not fail")
        for script in ["scrape-all.js", "reparse-characters.js"]:
            text = (scraper / "scripts" / script).read_text()
            if "backupDb" not in text:
                fails.append(f"scraper/scripts/{script} never calls backupDb before it starts changing the database")
            if "preflight" not in text.lower():
                fails.append(f"scraper/scripts/{script} never runs the preflight check")
        code, out = run(["node", "scraper/scripts/test-export-builder-catalog.js"])
        if code != 0:
            fails.append("the existing check test-export-builder-catalog.js broke:\n" + out[-600:])
    else:
        fails.append("usage: verify_scraper.py <catalog|preflight>")
finally:
    if made_data:
        shutil.rmtree(data, ignore_errors=True)
    if made_link and link.is_symlink():
        link.unlink()
for f in fails:
    print("FAIL:", f)
print("verify_scraper:", "passed" if not fails else f"{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
