# Domain Model

## Aggregate hierarchy
- `Client`
  - `SAPSystem`
    - `Assessment`
      - `PipelineRun`
      - `SourceFile`
      - `SAPObject`
      - `Evidence`
      - `Finding`
      - `BusinessRule`
      - `Application`
      - `CleanCoreAssessment`
      - `Recommendation`
      - `Embedding`

## Key distinctions
### SourceFile vs SAPObject
A file is a physical source. It may contain one or multiple SAP objects or subobjects. `SAPObject` references source location/range; file and object are never assumed to be equivalent.

### BusinessRule
Suggested fields:
- name, description, domain, rule type;
- condition, action, exception;
- confidence;
- related applications and SAP objects;
- supporting evidence.

Rule types: `VALIDATION`, `CALCULATION`, `DECISION`, `WORKFLOW`, `ELIGIBILITY`, `DERIVATION`, `COMPLIANCE`, `INTEGRATION`, `OTHER`.

### Application
Functional cluster of related SAP custom objects. Suggested fields:
- name, description, domain;
- parent application (optional);
- confidence and discovery rationale;
- member objects, transactions, business rules and findings.

### CleanCoreAssessment
Must separate:
- `technical_risk`: LOW/MEDIUM/HIGH/CRITICAL;
- `business_importance`: LOW/MEDIUM/HIGH/CRITICAL/UNKNOWN;
- `recommendation`: KEEP/REMEDIATE/MODERNIZE/REPLACE_WITH_STANDARD/REIMPLEMENT_AS_EXTENSION/RETIRE/REVIEW;
- confidence, rationale and evidence references.
