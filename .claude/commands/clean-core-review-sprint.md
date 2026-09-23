# /clean-core-review-sprint

Perform a read-only review of the active sprint. Do not modify code, documentation, Git state or lifecycle status.

Review:
- implementation against the active sprint scope;
- demonstrable outcome;
- minimal required checks and known failures;
- progress/state/handoff consistency;
- unresolved architectural conflicts;
- known limitations and backlog items;
- repository hygiene risks;
- migration readiness when schema changed.

Return a concise report ending with exactly one readiness verdict:

`READY_TO_FINISH: YES`

or

`READY_TO_FINISH: NO`

When NO, list the blocking reasons. Do not fix them in this command.
