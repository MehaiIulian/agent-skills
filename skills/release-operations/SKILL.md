---
name: release-operations
description: >-
  Execute pre-release verification gates, migration and rollback checks, CI/CD
  readiness, observability verification, and release checklist preparation in
  .aidlc/operation/release-checklist.md. Use during AI-DLC Operation before
  shipping or tagging a release.
license: MIT
metadata:
  phase: operation
  category: operation
  version: "1.0.0"
---

# Release Operations & Deployment Readiness (AI-DLC Operation)

Ensure changes are safe to deploy, observable in production, and straightforward to roll back.

## Step 1: Verify Pre-Release Gates

Confirm in `.aidlc/state.json` and recent tool outputs:
1. All Construction units are `approved` and `verifier` (plus `security` when applicable) signed off.
2. Full test suite, build, and repository validators pass after the final commit/edit.
3. Configuration changes, new env vars, and feature flags have safe defaults documented.

## Step 2: Validate Migrations & Rollback Path

- **Zero-Downtime / Backward Compatibility**: Verify schema, API, and config migrations support old and new versions during rollout (expand-and-contract when needed).
- **Explicit Rollback Steps**: Write numbered, tested rollback steps (revert commit/tag, flag disable, down-migration) in `.aidlc/operation/release-checklist.md` (using `skills/workflow/assets/release-checklist-template.md`).

## Step 3: Verify Observability & Runbooks

- Confirm critical failure paths emit structured logs/metrics or actionable exit codes without leaking secrets.
- Verify health checks, alerts, or operational runbooks reflect new services/endpoints.

## Handoff

Present `.aidlc/operation/release-checklist.md` plus final verification evidence to the user / `orchestrator` to clear the Operation gate (`state.py advance --to completed`).
