---
name: refactoring
description: >-
  Execute behavior-preserving structural improvements using characterization
  tests, small reversible steps, and continuous verification without mixing in
  unrelated feature changes. Use when simplifying complex modules, removing
  duplication, or paying down technical debt.
license: MIT
metadata:
  phase: construction
  category: construction
  version: "1.0.0"
---

# Safe Behavior-Preserving Refactoring

Improve internal structure, readability, and modularity while strictly preserving external behavior.

## Guardrails

1. **Separate Refactoring from Behavior Changes**: Do not mix structural cleanup with new features or bug fixes in the same step/commit unless required by an approved unit.
2. **Preserve Public Contracts & Docs**: Keep public signatures, error semantics, and unrelated docstrings intact unless explicitly refactoring an internal boundary.

## Procedure

1. **Baseline Characterization**:
   - Run existing tests first.
   - If the target module lacks test coverage, write **characterization tests** capturing current observable behavior (including edge cases) before changing a single line of production code.
2. **Identify Concrete Smells**:
   - Duplicated logic -> extract shared parameterized helper.
   - Deep nesting / monolithic function -> early returns + single-purpose helpers.
   - Special-case `if/elif` chains -> table/mapping-driven dispatch.
   - Tight coupling to I/O -> inject boundary dependency.
3. **Transform in Small Verified Steps**:
   - Apply one cohesive transformation at a time (extract helper, inline dead wrapper, rename, simplify).
   - Run the test suite after **every** step so regressions surface immediately within a tiny diff.
4. **Clean Up & Verify**:
   - Remove unused imports, dead variables, or obsolete helpers left behind.
   - Re-run tests, linter, and typechecker after the final edit.
5. **Document Changes**:
   - Update docstrings, comments, and README if the refactoring affects public-facing behavior or usage patterns.

## Handoff

Send a Handoff Envelope (`NEEDS_REVIEW`) to `verifier` highlighting that behavior was preserved and listing characterization + existing test results.
