# /clean-core-validate

Validate only the active sprint's critical PoC behavior without changing sprint lifecycle state.

Run as applicable:
- startup/smoke checks;
- newly introduced critical API/schema/domain contracts;
- the primary demonstrable user flow;
- explicitly required provider/MCP integration checks;
- Alembic migration applicability when schema changed;
- basic repository hygiene relevant to the sprint.

Do not expand into exhaustive coverage, load/performance suites, enterprise security testing or unrelated regression suites unless needed to diagnose a blocking defect.
