# Claude Code Instructions — SAP Clean Core Analysis PoC

## Mission
Implement the application described by this baseline sprint by sprint, preserving an executable and demonstrable state after every sprint.

## Sources of truth
Use documents in this order:
1. `docs/delivery/IMPLEMENTATION_BASELINE.md`
2. accepted ADRs in `docs/adr/`
3. sprint file currently active in `docs/delivery/EXECUTION_STATE.yaml`
4. architecture/domain/UX/AI documents
5. `docs/delivery/BACKLOG.md` only as future work, never as active scope unless promoted into a sprint
6. legacy documentation only as implementation reference

If documents conflict, the higher item wins. Do not infer enterprise requirements that the PoC explicitly excludes.

## Sprint execution rules
- One sprint = one local branch = one official commit on `main`.
- Sprint branch naming is canonical: `sprint/<NN>-<sprint-slug>`, derived from the sprint filename.
- `/clean-core-run-sprint` creates the sprint branch when needed or resumes it when already present.
- Re-running `/clean-core-run-sprint` after interruption must continue from persisted progress; do not restart validated work unnecessarily.
- Do **not** execute `git commit` during sprint development. The official sprint commit is created only by `/clean-core-finish-sprint`.
- Do not automatically start the next sprint after finishing the current sprint.
- `/clean-core-review-sprint` is read-only and evaluates readiness for closure.
- `/clean-core-finish-sprint` is the only command allowed to mark the sprint completed, generate its result record, commit it, fast-forward `main`, and delete the local sprint branch.
- The finish command must abort before commit if mandatory validations, documentation consistency, repository hygiene, or sprint Definition of Done fail.
- Do not push automatically unless the user explicitly asks for a push.

## Scope control
- Work only on the active sprint unless a prerequisite defect blocks it.
- If useful work is discovered but is not required by the active sprint, record it in `docs/delivery/BACKLOG.md` and continue the sprint.
- Do not silently change accepted architecture. If implementation requires contradicting an ADR or canonical architecture decision, record the conflict in progress/handoff and stop that part of the work for human decision.
- Local implementation details that do not alter architecture may be decided autonomously.

## Engineering principles
- Implement in small checkpoints and update sprint progress immediately after a validated checkpoint.
- Do not mark work complete merely because code was written. Run the sprint's minimal smoke/contract/critical-flow checks.
- Do not chase high test coverage. Tests protect critical PoC behavior only.
- Keep the application runnable after each checkpoint where practical.
- Long-running work must use durable persisted state; never rely solely on in-memory progress.
- Do not put Clean Core domain logic inside Electron/React. Domain processing belongs in Python backend modules.
- Do not couple domain services directly to Bedrock, Azure Foundry or MCP SDK details. Use adapters/interfaces.
- AI persisted outputs must be structured, schema validated, domain validated, and evidence-bound.
- AI outputs are interpretation, not factual evidence by themselves.
- Database schema evolution must use Alembic migrations once persistence is introduced.
- Prefer a small reproducible seed/demo dataset for fast validation of each new capability.
- Never commit secrets, customer assessment data, local databases, generated vector indexes, or local provider credentials.

## Target stack
- Desktop shell: Electron
- UI: React + TypeScript + Vite
- UI toolkit: Tailwind CSS + shadcn/ui
- Data/table: TanStack Query / TanStack Table
- Charts: Recharts
- Graph: React Flow
- Code viewer: Monaco Editor
- Backend: FastAPI + Python
- ORM: SQLAlchemy
- Database: PostgreSQL + pgvector
- Database migrations: Alembic
- LLM: AWS Bedrock and Azure AI Foundry
- SAP knowledge: `mcp-sap-docs`, `mcp-abap`
- Development: Docker Compose + Dev Container

## State and delivery files
- `docs/delivery/EXECUTION_STATE.yaml` — active sprint and global execution state.
- `docs/delivery/SPRINT-PROGRESS.template.yaml` — template for sprint progress files.
- `docs/delivery/SPRINT-RESULT.template.md` — template for the final sprint result record.
- `docs/delivery/SESSION_HANDOFF.md` — last known implementation state and restart notes.
- `docs/delivery/BACKLOG.md` — deferred ideas and out-of-scope discoveries.

## Completion rule
A sprint is ready to finish only when:
- planned capability is implemented or explicitly deferred with rationale;
- its primary user flow is demonstrable;
- minimal required checks pass;
- progress and handoff documentation are current;
- no unresolved architectural conflict is hidden;
- repository hygiene checks pass.

A sprint becomes **completed** only after `/clean-core-finish-sprint` succeeds.
