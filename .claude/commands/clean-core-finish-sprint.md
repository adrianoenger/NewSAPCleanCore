# /clean-core-finish-sprint

Formally finish the active sprint. This is the **only** project command allowed to create the official sprint commit, mark the sprint completed and publish it to the remote. On success the repository is left ready to start the next sprint.

## Preconditions
1. Read `CLAUDE.md`, implementation baseline, sprint execution model, active sprint, progress, execution state and handoff.
2. Confirm current branch equals the canonical sprint branch.
3. Confirm sprint implementation is ready for review/closure and no required capability remains pending without explicit accepted deferral.
4. Run the mandatory lean validation set. Abort on blocking failure.
5. If database schema changed, confirm Alembic migrations can be applied from the expected baseline.
6. Run repository hygiene checks. Abort if secrets, customer assessment data, local databases, generated indexes, build/runtime noise or other prohibited files would be committed.
7. Confirm no unresolved architectural conflict blocks closure.
8. Confirm the remote is reachable (`git fetch origin`) and that `origin/main` has not advanced beyond the sprint branch base (`git merge-base --is-ancestor origin/main HEAD`). If it has, abort and report: `main` could not be fast-forwarded and needs human resolution.

## Closure documentation
9. Generate `docs/delivery/results/SPRINT-XX-RESULT.md` using the result template, documenting delivered increment, demo path, checks, limitations and deferred backlog IDs.
10. Mark the sprint progress file `status: completed`, `progress_percent: 100`, set `completed_at`, clear current checkpoint, and set review/finish readiness to false after completion.
11. Update `SESSION_HANDOFF.md` with sprint completion and next-sprint readiness.
12. Update `EXECUTION_STATE.yaml`:
    - set `last_completed_sprint` to the active sprint;
    - clear `active_sprint`, `active_branch`, and checkpoint;
    - set active status to `not_started`;
    - set `next_sprint` to the next planned sprint (or null after the final sprint);
    - do not mark the next sprint started.

## Official Git closure
13. `git add -A`.
14. Review staged files one final time for prohibited data.
15. Create exactly one commit on the sprint branch using: `feat(sprint-NN): complete <concise sprint title>`.
16. Capture and report the resulting commit hash in the command output. Do not modify committed files merely to persist the hash; future status commands must derive it from Git history.
17. Push the sprint branch to the remote: `git push -u origin <sprint-branch>`.
18. Switch to `main`.
19. Fast-forward only: `git merge --ff-only <sprint-branch>`.
20. Synchronize remote `main`: `git push origin main`.
21. Delete the local sprint branch: `git branch -d <sprint-branch>` (the remote sprint branch is kept as the sprint record).
22. Update local `main` from the remote: `git pull --ff-only origin main`.
23. Verify: current branch is `main`, working tree is clean, local sprint branch is absent, `main` and `origin/main` point to the same commit, and `origin/<sprint-branch>` exists.

## Failure handling
- If any pre-commit step fails, abort and leave the sprint branch intact for correction.
- If a push fails after the commit exists, do not create another commit and do not delete the local sprint branch; report the failed step and the exact commands still pending so closure can be resumed.

## Prohibitions
- Do not create a merge commit.
- Do not create intermediate or follow-up sprint commits.
- Do not force-push.
- Do not start the next sprint.
