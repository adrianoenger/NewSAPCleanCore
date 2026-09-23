# Persistence Model

## Database
PostgreSQL with pgvector.

## Structured data
PostgreSQL is the source of truth for clients, systems, assessments, files, SAP objects, pipeline state, dependencies, ATC, findings, evidence, business rules, applications, Clean Core results and recommendations.

## Semantic data
Use pgvector for embeddings of meaningful semantic units, not indiscriminate raw-file chunks.

Recommended embedding entities:
- SAP object functional/technical understanding;
- business rule;
- finding;
- application;
- AI analysis summary;
- recommendation.

Each vector record should carry filterable metadata including `client_id`, `sap_system_id`, `assessment_id`, entity type/id, and application id when applicable.

## Version metadata for persisted AI outputs
Store at least:
- provider;
- model;
- prompt type/version;
- schema version;
- execution timestamp;
- confidence;
- source/input version where relevant.

## Schema evolution
Use Alembic migrations for schema changes after persistence is introduced. A developer should be able to bring an existing development database to the current sprint schema without manually recreating it as the normal path.

## Seed/demo data
Maintain a small synthetic seed dataset for reproducible sprint demonstrations. Seed content must not contain customer data or secrets.
