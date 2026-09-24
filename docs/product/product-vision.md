# Product Vision

## Objective
Create a PoC that reads large directories of SAP/ABAP artifacts, interprets them through a staged pipeline, stores structured and semantic knowledge, and exposes the result through modern visual exploration and an AI Copilot.

The product must prove that ABAP can be transformed into **business understanding and actionable Clean Core modernization guidance**, not merely parsed or linted.

## Target outcome
Given a completed assessment, the solution should answer:
- What custom applications exist?
- What business rules are implemented by them?
- Which SAP objects and dependencies support those applications?
- What technical and Clean Core risks exist?
- What evidence supports each conclusion?
- What does SAP guidance suggest for the relevant problem or extension pattern?
- What should be kept, remediated, modernized, replaced, reimplemented as an extension, retired, or reviewed?

## PoC boundaries
Included:
- multiple clients and assessments, with SAP source system stored as Assessment metadata;
- directory-based source ingestion;
- reusable parsing from the current solution;
- ATC ingestion;
- dependency discovery;
- AI-assisted understanding;
- business-rule and application discovery;
- SAP documentation MCP access;
- Clean Core assessment;
- embeddings and semantic retrieval;
- Dashboard Geral plus four result perspectives (Executive, Technical, Functional, Architecture);
- permanent AI Copilot;
- durable pause/resume/retry processing.

Explicitly excluded for this version:
- authentication and user management;
- RBAC/SSO;
- multi-tenant security isolation;
- enterprise audit trails;
- HA/DR;
- distributed microservices;
- enterprise observability;
- extensive security hardening;
- exhaustive test coverage;
- production-grade scaling.
