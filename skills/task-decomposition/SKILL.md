---
name: task-decomposition
description: >-
  Decompose an approved technical design into small, independently testable
  Units of Work with disjoint file ownership, explicit dependencies, and
  assigned agent skills. Use at the end of AI-DLC Inception before launching
  parallel Construction subagents or Swarm workers.
license: MIT
metadata:
  phase: inception
  category: inception
  version: "1.0.0"
---

# Task & Unit Decomposition (AI-DLC Inception -> Construction)

Parallel AI coding succeeds when file ownership is disjoint and unit contracts are unambiguous; it breaks when two workers modify the same file simultaneously.

## Step 1: Slice Into Vertical, Testable Units

Decompose `.aidlc/inception/design.md` into Units of Work (`U1`, `U2`, ...):
- **Right-Sized**: Each unit should be completable and verifiable independently (typically 1–5 source files + corresponding tests).
- **Contract-First**: If `U2` depends on a type or interface produced by `U1`, either mark `U2` blocked on `U1` or define the shared interface in a preceding foundation unit `U0`.

## Step 2: Enforce Disjoint File Ownership

Verify that **no two active concurrent units touch the same file**:
- Assign exact file paths (and test files) to each unit.
- Register every unit in `.aidlc/state.json` via `scripts/state.py`, which automatically rejects file collisions:
  ```bash
  python3 scripts/state.py register-unit \
    --project <project> \
    --id U1 \
    --title "Implement auth token service" \
    --owner developer \
    --files "src/auth/tokens.py,tests/test_tokens.py" \
    --skills "tdd-implementation,security-audit"
  ```

## Step 3: Assign Skills & Execution Order

For each unit specify:
1. **Owner & Model Tier**: e.g., `developer` (or dynamic subagent name).
2. **Required Skills**: e.g., `tdd-implementation`, `refactoring`, `technical-documentation`.
3. **Dependencies & Parallel Wave**: Group independent units into Wave 1 (parallel `workspace: "share"`), dependent units into Wave 2.
4. **Acceptance Criteria IDs**: Map back to `FR-*` / `NFR-*` in `.aidlc/inception/requirements.md`.

## Verification

- Every `FR-*` in `requirements.md` maps to at least one registered unit.
- `state.py register-unit` passes with zero file overlap errors across concurrent units.
- Present `.aidlc/inception/units.md` (and `requirements.md` / `design.md`) at the Inception gate before advancing to Construction.
