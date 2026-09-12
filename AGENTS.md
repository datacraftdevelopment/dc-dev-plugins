# Working on dc-dev-plugins in Codex

Read `CLAUDE.md` for shared repository conventions. Develop in place; this checkout
is the source of truth. For changes inside `fm-dc`, also read `fm-dc/CLAUDE.md`.

`scripts/build_codex.py` generates Codex editions from tracked plugin files.
Keep Claude source behavior compatible, put host adaptation in the builder, and
never edit `.codex-build/` or the installed `~/plugins/` copies as source.
Run `python3 -m unittest discover -s tests -v` after builder changes and validate
the generated plugins. Installation/update instructions are in `docs/codex.md`.
