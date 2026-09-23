# /clean-core-finish-sprint

Formally finish the active sprint. This is the **only** project command allowed to create the official sprint commit and mark the sprint completed.

## Preconditions
1. Read `CLAUDE.md`, implementation baseline, sprint execution model, active sprint, progress, execution state and handoff.
2. Confirm current branch equals the canonical sprint branch.
3. Confirm sprint implementation is ready for review/closure and no required capability remains pending without explicit accepted deferral.
4. Run the mandatory lean validation set. Abort on blocking failure.
5. If database schema changed, confirm Alembic migrations can be applied from the expected baseline.
6. Run repository hygiene checks. Abort if secrets, customer assessment data, local databases, generated indexes, build/runtime noise or other prohibited files would be committed.
7. Confirm no unresolved architectural conflict blocks closure.

## Closure documentation
8. Generate `docs/delivery/results/SPRINT-XX-RESULT.md` using the result template, documenting delivered increment, demo path, checks, limitations and deferred backlog IDs.
9. Mark the sprint progress file `status: completed`, `progress_percent: 100`, set `completed_at`, clear current checkpoint, and set review/finish readiness to false after completion.
10. Update `SESSION_HANDOFF.md` with sprint completion and next-sprint readiness.
11. Update `EXECUTION_STATE.yaml`:
    - set `last_completed_sprint` to the active sprint;
    - clear `active_sprint`, `active_branch`, and checkpoint;
    - set active status to `not_started`;
    - set `next_sprint` to the next planned sprint (or null after the final sprint);
    - do not mark the next sprint started.

## Official Git closure
12. `git add -A`.
13. Review staged files one final time for prohibited data.
14. Create exactly one commit using: `feat(sprint-NN): complete <concise sprint title>`.
15. Capture and report the resulting commit hash in the command output. Do not modify committed files merely to persist the hash; future status commands must derive it from Git history.
16. Switch to `main`.
17. Fast-forward only: `git merge --ff-only <sprint-branch>`.
18. Delete the local sprint branch: `git branch -d <sprint-branch>`.
19. Verify current branch is `main`, working tree is clean, and the local sprint branch is absent.

## Prohibitions
- Do not create a merge commit.
- Do not create intermediate or follow-up sprint commits.
- Do not start the next sprint.
- Do not push to remote unless the user explicitly requested it.

If any pre-commit closure step fails, abort and leave the sprint branch intact for correction.
