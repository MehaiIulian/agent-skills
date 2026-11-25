---
name: systematic-debugging
description: >-
  Diagnose bugs and failing tests through a scientific Reproduce-Isolate-
  Hypothesize-Regression-Fix-Verify loop with an explicit anti-thrashing rule.
  Use when investigating runtime errors, flaky tests, regressions, or unexpected
  tool failures.
license: MIT
metadata:
  phase: construction
  category: construction
  version: "1.0.0"
---

# Systematic Debugging

Replace trial-and-error edits with disciplined root-cause isolation.

## 1. Reproduce Deterministically

- Capture the exact failing command, inputs, environment/config state, and full error trace.
- Never theorize from a truncated error message; inspect the real failure output and surrounding source lines.

## 2. Isolate & Narrow the Blast Radius

- Identify the exact boundary where actual behavior diverges from expected behavior (input parsing, state transition, external API, concurrency/ordering).
- Inspect recent `git diff` / `git log` changes if the issue is a regression.

## 3. Form One Falsifiable Hypothesis

State explicitly before making any edit:
- **Hypothesis**: *"`X` happens because `Y` produces `Z` when condition `W` holds."*
- **Check**: How a minimal diagnostic or targeted test confirms or refutes it.

> **Anti-Thrashing Rule**: If **2 consecutive fix attempts** based on your hypotheses fail to resolve the issue, **STOP editing**. Re-read the full execution path, question your underlying assumptions about the framework/state, or escalate with a structured `BLOCKED` handoff to `orchestrator` / human.

## 4. Write a Regression Test First (`Red`)

Before applying the fix, encode the reproduction in a minimal automated test that fails cleanly on the buggy code.

## 5. Apply Root-Cause Fix & Verify (`Green`)

- Fix the underlying cause (not a symptom-masking `try/except` or retry band-aid).
- Run the new regression test AND the broader test suite after your final edit.
- Document root cause, fix location (`file:line`), and verified command output in your response or Handoff Envelope.
