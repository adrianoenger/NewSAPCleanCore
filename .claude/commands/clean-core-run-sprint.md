# /clean-core-run-sprint

Execute the sprint identified by `docs/delivery/EXECUTION_STATE.yaml` autonomously until completion or a genuine blocker.

1. Read `CLAUDE.md`, implementation baseline, active sprint, progress file and relevant ADRs.
2. Resume from the first incomplete capability/checkpoint; do not repeat validated work unnecessarily.
3. Implement in small checkpoints.
4. After each checkpoint, run only the minimal validations required by the sprint and update progress.
5. Correct failures before advancing when they block the sprint's demonstrable outcome.
6. Do not stop merely to ask for routine implementation choices already decided by the documentation.
7. If a decision is genuinely absent and materially architectural, record the blocker in progress/handoff and stop cleanly.
8. On sprint completion, update `EXECUTION_STATE.yaml`, `SESSION_HANDOFF.md`, and sprint progress.
