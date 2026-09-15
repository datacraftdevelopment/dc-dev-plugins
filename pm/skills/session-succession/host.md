# Host operations — Claude

Discover the available session creation, status, message and close controls in
the **current host** and read their contracts. The pilot used `spawn_task`,
`list_sessions` and `send_message`; those names are observations, not a promise
that every Claude app or CLI exposes them. Check same-checkout startup support:
this beta needs a sequential successor in the recorded checkout. If creation
only offers a fresh worktree, leave the handoff prepared and report that mismatch.

The user's explicit succession instruction must authorize creating the next
session. Use that permission without repeating the question. A subagent is not
a substitute for a fresh orchestrator session. Use Ringer for autonomous workers;
use the host's session-creation control only for orchestrator replacement.

Keep successors on the **ordinary session tier: Opus for Claude Code**. Astra
and Fable remain Ringer review seats; successor creation never promotes the
interactive orchestrator to a reviewer model. When the host can select the model,
select `claude-opus-5`; preserve the user's explicit model choice when it differs.

Prepare the self-contained [successor prompt](prompt.md), filled with actual values.

The helper generates no host call and supplies no host identity. Obtain IDs from
actual host state. Put the launch attempt in the title as well as the prompt when
the host supports a title, so an interrupted creation can be reconciled.

Use `launch` once to obtain the attempt before submitting the completed prompt.
If `dispatch_allowed` is false, inspect status; do not submit another create call.
Record the returned successor ID with `created`. If the result is queued or a
click-to-start chip, report it as created/pending, never running. A completion
notification or sent message alone is not the successor's PM acknowledgement.

If controls are absent, preserve `prepared`, expose the compact next-session
prompt and report **manual startup required**. Do not start detached Claude CLI
processes as an undocumented fallback. If the user starts the successor manually,
reserve launch and include its attempt in the prompt so it can acknowledge.

After the successor acknowledges, release this session's own resources and record
`retire`. Close/archive only via supported controls. If self-close is unavailable,
leave the session quiescent with a final successor link and report host closure
unconfirmed. Whether a retired UI session releases memory is a live beta measure.
