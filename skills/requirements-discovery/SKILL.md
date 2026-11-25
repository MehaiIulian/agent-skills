---
name: requirements-discovery
description: >-
  Conduct structured requirements discovery, ambiguity resolution,
  functional and non-functional requirements (NFR) specification, and testable
  Given/When/Then acceptance criteria. Use during AI-DLC Inception before design
  or implementation begins.
license: MIT
metadata:
  phase: inception
  category: inception
  version: "1.0.0"
---

# Requirements Discovery (AI-DLC Inception)

Translate raw user intent into verifiable, unambiguous requirements before writing design docs or production code.

## Step 1: Ground Intent & Existing Business Rules in Current Reality

1. Inspect existing repository docs, domain services, validators, API schemas, and tests (delegate broad sweeps to `researcher` via `invoke_subagent`).
2. Extract **existing application business rules** (domain invariants, state transition rules, authorization/ownership policies, limits/calculations) that must be preserved or intentionally evolved.
3. Identify actors/personas, primary workflows, external integrations, and existing constraints.

## Step 2: Surface and Resolve Ambiguities Early

List hidden assumptions across:
- **Business Rules & Domain Policies**: eligibility conditions, allowed/forbidden state transitions, calculation formulas, conflict resolution, domain exceptions.
- **Behavior & Edge Cases**: empty states, concurrency, retries, idempotency, failure modes.
- **Data & Contracts**: schema compatibility, migrations, validation rules, error payloads.
- **Non-Functional Requirements (NFRs)**: authentication/authorization, latency/throughput bounds, observability, backward compatibility, platform support.

Ask focused, high-leverage clarifying questions (`ask_question` with recommended defaults when options are clear) rather than guessing business rules silently.

## Step 3: Write Testable Requirements (`.aidlc/inception/requirements.md`)

Populate `.aidlc/inception/requirements.md` using the structure from `skills/workflow/assets/requirements-template.md`:
1. **Business Rules (`BR-1`, `BR-2`, ...)**: Document both existing business rules that must hold and new/updated business policies, with clear trigger conditions and rejection/enforcement rules.
2. **Functional Requirements (`FR-1`, `FR-2`, ...)**: Every requirement MUST include concrete **Given / When / Then** acceptance criteria (referencing applicable `BR-*` IDs) so `developer` and `verifier` can test against it directly.
3. **NFRs**: Quantify constraints where measurable (e.g., timeouts, max payload sizes, auth scopes).
4. **Explicit Non-Goals**: Name out-of-scope features to prevent scope creep during Construction.
5. **Resolved Decisions Log**: Record every human or architectural answer with rationale.

## Verification & Handoff

- **Self-Check**: Can an engineer write automated acceptance tests solely from each `FR-*` without guessing inputs or error behavior?
- **Next Peer**: Hand `.aidlc/inception/requirements.md` to `architecture-ddd` (`architect`) with Handoff status `READY`.
