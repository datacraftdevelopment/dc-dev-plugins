# Choose the billing rounding rule
Status: ready
Type: task
Gate: human
Blocked by: 02

Billed time needs rounding. Options are rounding each entry up to 6 minutes (0.1 hour), each entry up to 15 minutes, or the daily total per client up to 15 minutes. The sample has a 7-minute entry (Acme, 30 Sep) where these give different answers. This changes what clients are invoiced, so it needs Joe.

On go: implement the chosen rule as `hours/billing.py` `billable(entries)`, with tests that pin the 7-minute case.
