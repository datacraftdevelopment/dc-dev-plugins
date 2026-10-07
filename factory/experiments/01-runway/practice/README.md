# Practice target: hours

A tiny Python tool (no dependencies) with six tickets for Runway's first real run. Four are AFK, and two are marked `Gate: human` because they're real judgment calls: how billing rounds time, and which report formats are worth having.

```bash
bash setup.sh                       # creates ~/Agentic-Mini/_Sandbox/runway/runway-practice
python3 ../runway.py --root ~/Agentic-Mini/_Sandbox/runway/runway-practice loop
python3 ../runway.py --root ~/Agentic-Mini/_Sandbox/runway/runway-practice status
```

`runway.json` is copied into the practice repo; edit it there. The prepared order is:

| Ticket | Gate | Blocked by | Expected |
|---|---|---|---|
| 01 Parse entries | auto | | runs first |
| 02 Totals per client | auto | 01 | runs |
| 03 Billing rounding | **human** | 02 | packet prepped at the start; waits for your go |
| 04 CLI report | auto | 02 | runs |
| 05 Report format | **human** | 04 | packet prepped at the start; waits for your go |
| 06 README usage | auto | 04 | runs |

So the first `loop` should finish 01, 02, 04 and 06 and stop with two packets waiting. After two `go`s, a second `loop` runs 03 and 05. Target: 2 touches for 6 tickets.

**(unverified)** The `--allowedTools` syntax in `runway.json` is from memory. If the first ticket parks with a permissions error, that's the thing to fix.
