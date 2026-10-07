# Parse time entries from CSV
Status: ready
Type: task

Add `hours/entries.py` with `load(path)` that reads a CSV shaped like `data/sample.csv` and returns a list of entries with date, client, project, note, and duration in minutes (end minus start). Reject rows where end is before start with a clear error.

Done when: unit tests in `tests/test_entries.py` cover a normal row, the sample file, and the end-before-start error, and `python3 -m unittest discover -s tests` passes.
