---
name: incident-postmortem
description: >-
  Guide mitigation-first incident response, accurate timeline reconstruction,
  blameless root-cause and contributing-factor analysis, and concrete preventive
  action items that feed back into AI-DLC Inception. Use during production
  incidents or post-incident reviews.
license: MIT
metadata:
  phase: operation
  category: operation
  version: "1.0.0"
---

# Incident Triage & Blameless Postmortem

Restore service safety first; learn systematically second; feed permanent fixes back into AI-DLC Inception.

## Phase 1: Mitigation First (During Active Incident)

1. **Assess Impact & Scope**: Which users, regions, endpoints, or data pipelines are degraded right now?
2. **Stabilize Before Deep Debugging**: Prioritize safe mitigation (rollback latest deploy, toggle feature flag, shed load, scale capacity, rotate compromised credentials) over risky live hotfixes.
3. **Preserve Evidence**: Capture logs, metrics snapshots, exact error traces, and recent commit/config SHAs before restarting or wiping instances.

## Phase 2: Blameless Postmortem Analysis

Document in `.aidlc/operation/postmortem-<YYYY-MM-DD>.md`:
1. **Executive Summary**: Impact, duration (start -> detection -> mitigation -> resolution), and severity.
2. **Verified Timeline (UTC)**: Timestamped sequence of triggers, alerts, actions, and outcomes.
3. **Root Cause & Contributing Factors**: Technical mechanism plus systemic gaps (missing test, absent timeout/circuit breaker, missing alert, ambiguous spec) — focus on systems, never blame individuals.
4. **What Worked / What Slowed Recovery**: Detection latency, runbook accuracy, rollback speed.

## Phase 3: Concrete Preventive Actions -> AI-DLC Inception

Create tracked follow-ups with owners and verification criteria:
- Immediate regression test (`tdd-implementation`)
- Architectural/guardrail hardening (`architecture-ddd`)
- Monitoring/alert or runbook update (`release-operations`)
Feed major fixes into a new AI-DLC `standard` or `deep` cycle.
