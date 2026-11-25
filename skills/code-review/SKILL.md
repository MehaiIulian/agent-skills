---
name: code-review
description: >-
  Perform adversarial, evidence-based code reviews against specifications and
  tests, producing severity-ranked findings with exact file:line citations and
  an APPROVED or CHANGES_REQUESTED verdict. Use during AI-DLC Construction
  verification or peer pull request reviews.
license: MIT
metadata:
  phase: construction
  category: verification
  version: "1.0.0"
---

# Adversarial Code Review (AI-DLC Verifier)

Review changes objectively against `.aidlc/inception/` specifications, invariants, and real test runs. Never edit production files during a verification pass.

## Step 1: Gather Evidence

1. Inspect the full diff (`git diff` / changed files) and the unit's acceptance criteria.
2. Read the modified files in context (callers, interfaces, error paths, tests) — do not review diff hunks in isolation.
3. Run the actual test suite, typechecks, and linters via `run_command`. Record exact commands and outputs.

## Step 2: Audit Using the Review Checklist

Evaluate the change against [references/review-checklist.md](references/review-checklist.md):
- Correctness, edge cases, and specification traceability
- State/concurrency safety and resource cleanup
- Error handling (no swallowed exceptions or silent fallbacks)
- Test rigor (real assertions, non-mocked integration boundaries where feasible)
- Code clarity (no duplicated logic, clean modular helpers)

## Step 3: Classify Findings & Render Verdict

Assign each verified issue a severity:
- **`CRITICAL`**: Correctness bug, data corruption/loss, security vulnerability, or failing tests. (**Blocks approval**)
- **`HIGH`**: Missing acceptance criterion, unhandled failure mode, race condition, or broken contract. (**Blocks approval**)
- **`MEDIUM`**: Maintainability issue, duplicated logic, or missing edge-case test.
- **`LOW`**: Minor clarity improvement or nitpick.

Verdict rules:
- Any `CRITICAL` or `HIGH` finding OR failing check -> **`CHANGES_REQUESTED`**
- Zero `CRITICAL`/`HIGH` findings AND all checks pass -> **`APPROVED`**

## Handoff

Send findings with exact `file:line`, observed evidence, and concrete remediation directly to the author (`send_message` or Swarm `@mention`). Copy `APPROVED` verdicts to `orchestrator` and update `.aidlc/construction/verification-report.md`.
