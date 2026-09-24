# /clean-core-run-sprint

Start or resume the sprint identified by `docs/delivery/EXECUTION_STATE.yaml` and continue autonomously until the sprint implementation is ready for review or a genuine blocker is reached.

1. Read `CLAUDE.md`, implementation baseline, sprint execution model, accepted ADRs, execution state, active/next sprint file, progress file if present, and session handoff.
2. Run preflight checks:
   - when starting a new sprint, current branch must be `main` and working tree must be clean;
   - when starting a new sprint, sync local `main` with the remote: `git fetch origin` then `git pull --ff-only origin main`; abort if `main` cannot be fast-forwarded (diverged history needs human resolution);
   - previous sprint must be completed or this must be the initial sprint;
   - no secret/customer/runtime data may be staged.
3. Resolve the canonical sprint branch from the sprint filename (`sprint/<NN>-<sprint-slug>`).
4. If the sprint has not started, **always** create the canonical sprint branch from the synced `main` (`git switch -c <sprint-branch>`), initialize progress from the template, and update execution state to `in_progress`.
5. If the sprint is already in progress, reuse/switch to its existing canonical branch and resume from the first incomplete capability/checkpoint.
6. All checkpoints, development and progress/state updates happen on the sprint branch — never on `main`.
7. Implement in small checkpoints, run only the sprint's minimal validations, and persist progress after each validated checkpoint.
8. Record useful but out-of-scope discoveries in `docs/delivery/BACKLOG.md`; do not expand sprint scope silently.
9. If an accepted architectural decision must be contradicted, record the conflict in progress/handoff and stop only the affected work for human resolution.
10. Correct blocking failures before advancing. Routine implementation choices already covered by the documentation should not require user confirmation.
11. When all sprint implementation capabilities are complete and the demonstrable flow works, set `ready_for_review: true`, update handoff, and stop.

## Git rule
Do **not** execute `git commit`, merge, delete the sprint branch, push, or start the next sprint. Formal closure belongs exclusively to `/clean-core-finish-sprint`.
