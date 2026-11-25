---
name: architecture-ddd
description: >-
  Produce Domain-Driven Design (DDD) models, C4 architecture diagrams
  (Context, Container, Component, Code), bounded contexts, explicit module
  interfaces, failure-mode analyses, and Architecture Decision Records (ADRs) in
  .aidlc/inception/design.md. Use during AI-DLC Inception for standard or deep
  changes before breaking work into units.
license: MIT
metadata:
  phase: inception
  category: inception
  version: "1.0.0"
---

# Architecture, Domain-Driven Design & C4 Diagrams (AI-DLC Inception)

Produce clear domain boundaries, crisp module interfaces, **C4 architecture diagrams**, and documented trade-offs before decomposing work into implementation units.

## Step 1: Domain-Driven Design (DDD) & Business Rule Mapping

1. **Bounded Contexts**: Identify which domain boundary owns each concept and where translation/anti-corruption layers belong.
2. **Ubiquitous Language**: Define exact canonical names for entities, value objects, events, and errors so specs, types, and APIs share one vocabulary.
3. **Aggregates, Invariants & Business Rules (`BR-*`)**: Map every Business Rule (`BR-*` from `.aidlc/inception/requirements.md`) to the exact aggregate, domain policy, or validator that enforces it so business rules never leak into scattered UI/controller checks.

## Step 2: C4 Architecture Diagrams (L1–L4)

Follow [references/c4-diagrams.md](references/c4-diagrams.md) to include C4 diagrams in `.aidlc/inception/design.md`:
- **`standard` depth**: Generate **C4 Level 3 (Component)** showing internal modules, ports/adapters, and where `BR-*` rules live (plus **Level 2 (Container)** if crossing process/storage/service boundaries).
- **`deep` depth** (or on user request): Generate **C4 Level 1 (System Context)** + **Level 2 (Container)** + **Level 3 (Component)** (and **Level 4 (Code / Domain Class)** for complex aggregates).
- Label every node with `Name`, `[Type / Technology]`, and 1-line responsibility; label every arrow with the action and protocol/contract.

## Step 3: Component & Contract Design

Define only the concrete interfaces needed—avoid speculative abstractions:
- **Public Signatures & Schemas**: Request/response shapes, CLI arguments, database constraints, event schemas.
- **Dependency Direction**: Keep domain logic pure and isolated from I/O/framework details where practical.
- **Failure Modes**: Explicitly specify timeouts, partial-failure handling, idempotency, and error propagation.

## Step 4: Architecture Decision Records (ADRs)

For every significant technical choice (storage engine, protocol, library, migration strategy, concurrency model), record an ADR using [assets/adr-template.md](assets/adr-template.md) inside `.aidlc/inception/design.md` (or `.aidlc/inception/adr-NNN.md`):
- Context and forces
- Decision made
- Considered alternatives and concrete trade-offs
- Reversibility / migration path

## Step 5: Security & Architecture Gate

- For `deep` runs or designs touching auth, network edges, PII, secrets, or infra: send `.aidlc/inception/design.md` to `security` (`send_message`) for pre-implementation threat review.
- **Next Peer**: Proceed to `task-decomposition` to split the approved design into disjoint Work Units.
