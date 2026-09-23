# Claude Code Instructions — SAP Clean Core Analysis PoC

## Mission
Implement the application described by this baseline, sprint by sprint, preserving an executable and demonstrable state after every sprint.

## Sources of truth
Use documents in this order:
1. `docs/delivery/IMPLEMENTATION_BASELINE.md`
2. accepted ADRs in `docs/adr/`
3. sprint file currently marked active in `docs/delivery/EXECUTION_STATE.yaml`
4. architecture/domain/UX/AI documents
5. legacy documentation only as implementation reference

If documents conflict, the higher item wins. Do not infer enterprise requirements that the PoC explicitly excludes.

## Execution principles
- Work only on the active sprint unless a prerequisite defect blocks it.
- Implement in small checkpoints and update sprint progress immediately after a validated checkpoint.
- Do not mark work complete merely because code was written. Run the sprint's minimal smoke/contract/critical-flow checks.
- Do not chase high test coverage. Tests protect critical PoC behavior only.
- Keep the application runnable after each checkpoint where practical.
- Long-running work must use durable persisted state; never rely solely on in-memory progress.
- Do not put Clean Core domain logic inside Electron/React. Domain processing belongs in Python backend modules.
- Do not couple domain services directly to Bedrock, Azure Foundry or MCP SDK details. Use adapters/interfaces.
- AI persisted outputs must be structured, schema validated, domain validated, and evidence-bound.
- AI outputs are interpretation, not factual evidence by themselves.
- Never commit secrets. `.env` files containing credentials are local-only and must be ignored.

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
- LLM: AWS Bedrock and Azure AI Foundry
- SAP knowledge: `mcp-sap-docs`, `mcp-abap`
- Development: Docker Compose + Dev Container

## State files
- `docs/delivery/EXECUTION_STATE.yaml` — active sprint and global state.
- `docs/delivery/SPRINT-PROGRESS.template.yaml` — template for sprint progress files.
- `docs/delivery/SESSION_HANDOFF.md` — last known implementation state and restart notes.

## Completion rule
A sprint is complete only when:
- planned capability is implemented;
- its primary user flow is demonstrable;
- minimal defined checks pass;
- execution/progress documentation is updated.
