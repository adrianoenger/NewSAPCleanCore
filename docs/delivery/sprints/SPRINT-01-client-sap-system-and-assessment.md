> **SUPERSEDED TARGET MODEL (2026-09-24):** This sprint file documents the scope that was implemented historically. ADR-015 and Implementation Baseline R3.1 replace `Client → SAPSystem → Assessment` with `Client → Assessment` plus `Assessment.sap_source_system`. Do not use this file as the current domain target.

# SPRINT-01 — Client, SAP System and Assessment

## Goal
Implement the core navigation hierarchy.

## Planned capabilities
- Persist Client, SAPSystem and Assessment entities.
- Create CRUD-light APIs necessary for PoC creation/listing.
- Build Client Hub and system/assessment navigation.
- Keep current context visible in top bar.
- Extend the synthetic seed/demo data with at least one Client, SAP System and Assessment for reproducible navigation.

## Demonstrable outcome
Create a client, SAP system and assessment, then reopen and navigate back to it.

## Minimal validation
- Primary user flow for this sprint works.
- Relevant smoke test(s) pass.
- Critical API/schema/domain contracts introduced by this sprint are validated.
- Do not add broad test coverage unrelated to the demonstrated capability.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated.
- Application remains runnable for the next sprint.
