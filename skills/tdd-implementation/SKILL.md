---
name: tdd-implementation
description: >-
  Implement Units of Work using disciplined Red-Green-Refactor Test-Driven
  Development against acceptance criteria, maintaining strict file-ownership
  boundaries and test quality. Use during AI-DLC Construction for writing new
  features or behavioral changes.
license: MIT
metadata:
  phase: construction
  category: construction
  version: "1.0.0"
---

# TDD Implementation (AI-DLC Construction)

Build every assigned Unit of Work using tight **Red -> Green -> Refactor** cycles grounded in `.aidlc/inception/requirements.md` and `.aidlc/inception/design.md`.

## Step 1: Confirm Unit Scope & Baseline

1. Read your assigned unit spec, owned files, and acceptance criteria (`FR-*` / `NFR-*`). Do **not** edit files outside your unit boundary.
2. Run existing related tests first via `run_command` to confirm a clean baseline before editing.

## Step 2: Red — Write Failing Tests First

Translate each acceptance criterion and key edge case into focused automated tests:
- Cover happy path, boundary values, empty/null inputs, error/timeout paths, and invariants.
- Keep tests **deterministic and isolated** (no reliance on wall-clock sleeps, real network calls, or shared mutable globals; use temp dirs/fakes where appropriate).
- Run the new tests and verify they **fail for the expected reason** (missing behavior, not syntax/import mistakes).

## Step 3: Green — Implement Minimal Clean Behavior

1. Write the simplest clean implementation satisfying the tests and module interfaces.
2. Reuse existing repo helpers/patterns rather than duplicating logic.
3. Run the unit tests and confirm 100% pass without skipped or weakened assertions.

## Step 4: Refactor & Self-Audit

1. Remove duplication, flatten deep nesting with early returns, and add concise docstrings on new public functions/classes.
2. Run the full relevant test suite, linter, and typechecker (if configured) **after your final edit**.
3. Self-check diff scope to confirm zero unintended file edits or debug leftovers.

## Handoff

Update `.aidlc/state.json` (`update-unit --status in_review`) and send a Handoff Envelope (`NEEDS_REVIEW`, with exact commands and counts observed) to `verifier` via `send_message` or Swarm `@verifier`.
