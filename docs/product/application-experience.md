# Application Experience

## Current canonical framing
The application is Assessment-centric. It opens on an Assessments Home grid without a left sidebar. `Client → Assessment` is the managed hierarchy; the SAP source system is Assessment metadata. The left processing/results menu appears only after opening an Assessment, while the AI Copilot remains on the right.
 — SAP Clean Core Analyzer

**Status:** Product baseline for PoC

## 1. Product experience statement

A aplicação transforma customizações SAP, inicialmente compreensíveis principalmente por inspeção de código e conhecimento especializado, em um **modelo inteligente e navegável** que conecta:

- objetivo da aplicação;
- processos e regras de negócio;
- objetos ABAP;
- dependências;
- findings técnicos;
- aderência Clean Core;
- evidências;
- oportunidades de modernização.

## 2. Personas

### Executive

Needs: risk, complexity, impact, priority, modernization opportunity.

Primary views: Executive Overview, Modernization Opportunities.

### SAP Architect

Needs: architecture, dependencies, Clean Core, integrations, modernization strategy.

Primary views: Architecture View, Clean Core Findings, Application Discovery.

### Functional Specialist

Needs: processes, rules, behavior and business dependencies.

Primary views: Functional View, Application Discovery.

### Developer

Needs: code, objects, methods, dependencies and technical evidence.

Primary views: Technical View, Clean Core Findings, Architecture View.

## 3. Core views

### Applications

Portfolio/list of analyzed SAP applications with concise indicators: objects, dependencies, business rules, Clean Core findings/score and risk/priority.

### New SAP Analysis

Connect/select SAP source and start discovery. The target architecture uses direct SAP collection through RFC/PyRFC integrated into the Python pipeline. The same ingestion area may also attach optional supplemental evidence datasets (Panaya ETL, SAP Signavio Process Insights, FUE User Validation) through provider adapters; these enrich rather than replace canonical SAP source acquisition.

### Analysis Run

Shows the analysis pipeline and progress across stages such as:

1. SAP Object Collection
2. Object Understanding
3. Dependency Discovery
4. Business Rule Discovery
5. Application Discovery
6. Clean Core Analysis
7. Insight Generation

### Executive Overview

Business-oriented summary with application purpose, principal risks, Clean Core assessment and modernization signals.

### Architecture View

Interactive dependency graph connecting custom code, SAP standard, released APIs, legacy integration and Clean Core risk. This is the first high-fidelity reference view.

### Clean Core Findings

Evidence-based findings with severity, object, category, business/technical impact and recommended approach.

### Functional View

Business-readable rules extracted from the implementation, with confidence and source evidence.

### Technical View

SAP object tree + ABAP code viewer + contextual annotations for rule, dependency, finding, standard call and technical debt.

### Application Discovery

Narrative and structural explanation of purpose, processes, capabilities, entry points, integrations, data objects and critical execution flows.

### Modernization Opportunities

Presents options such as Keep, Refactor, Replace with SAP Standard, Side-by-Side Extension, Released API or Redesign. These are decision-support recommendations, not automatic approvals.

## 4. Cross-view continuity

Every view must share application/run context and participate in bidirectional navigation. Example journey:

`Executive risk → finding → rule → object → method/lines → dependency graph → modernization option`

The Copilot accompanies the journey and should not lose contextual continuity during navigation.

## 5. Traceability principle

AI-generated interpretation must be distinguishable from evidence. When the user explores a rule, finding or recommendation, the UI must provide a path back to the source material used in the analysis.

## 6. Analysis runs

The product should treat an analysis as a versioned run rather than an ephemeral result. The UX should support, progressively:

- run identity;
- completed/in-progress state;
- last analyzed timestamp;
- re-run;
- compare runs;
- view changes.

The PoC may implement these capabilities incrementally, but the information architecture must not block them.
