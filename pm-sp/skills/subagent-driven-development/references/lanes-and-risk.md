# Lanes and risk tiers (pm-sp)

Part of pm-sp:subagent-driven-development. Both come from the plan:
writing-plans adds the `## Lanes` section and a `**Risk:**` line per task.

## Lanes

**Lanes run at the same time** (pm-sp). When the plan has a `## Lanes`
section, don't wait for one lane to finish before starting the next. Once
the task a lane waits for is complete, dispatch that lane's implementer
straight away, alongside the other lanes', each in its own worktree on its
own branch cut from the plan's branch (the Agent tool's worktree isolation
where the host has it, otherwise pm-sp:using-git-worktrees under
`.superpowers/worktrees/`). Tasks inside a lane still run one after
another. Record BASE per lane, run each lane's reviews from its worktree,
and tag ledger lines with the lane. When a lane is complete, merge its
branch into the plan's branch, run the tests there, and only then start a
task that waits on it. A plan with no Lanes section runs one task at a
time; if you can see disjoint tasks it missed, rule them into lanes in the
ledger and run them the same way. Three implementers at once is the
ceiling.

## Risk tiers

**Scaled by risk** (pm-sp). The plan tags each task `**Risk:**`. A **high**
task gets SKILL.md's task review, every time. An **ordinary** or **low**
task skips it: the implementer's tests and self-review stand, and the
whole-branch review at the end covers it, with every ordinary and low task
named in that review's brief. A task with no Risk line is high. If an
implementer's report shows the task touched data correctness, security or
an external contract after all, raise it to high and review it. Ledger
line: `Task <N>: complete (commits …, risk <tier>, no task review)`.

## Screens

A task that builds or changes a screen (pm-sp) isn't complete until its
screenshots, every view it touches on real data at a real window size, are
in the plan's workspace and match the approved screens. Reviews read code;
only a look catches a broken layout.
