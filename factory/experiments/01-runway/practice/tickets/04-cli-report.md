# Command-line report
Status: ready
Type: task
Blocked by: 02

Add `hours/__main__.py` so `python3 -m hours report data/sample.csv` prints, per client, each project's hours to two decimals and a client total. Plain text table, no dependencies.

Done when: a test runs the command through `subprocess` on the sample file and checks the Acme total line, and the suite passes.
