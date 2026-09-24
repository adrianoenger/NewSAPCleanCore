# ADR-010 — Permanent Right-Side AI Copilot

**Status:** Accepted — revised 2026-09-24  
**Date:** 2026-09-23

## Decision
Keep the AI Copilot permanently mounted on the right side of the application, including both **Assessments Home** and all screens inside an Assessment. It follows UI context, accepts added entities/source selections, and returns navigable references without automatically mutating Assessment state.

The absence of the left sidebar on Assessments Home does not change this rule.

## Consequence
Implementation and sprint acceptance criteria must preserve Copilot continuity across home, processing stages and result views. Any future change requires updating or superseding this ADR.
