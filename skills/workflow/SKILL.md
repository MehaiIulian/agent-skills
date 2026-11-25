---
name: workflow
description: >-
  Run an end-to-end AI-Driven Development Life Cycle (AI-DLC) workflow from
  adaptive triage through Inception, Construction, and Operation with
  configurable human verification gates and .aidlc/ state tracking. Use when
  starting, resuming, or managing a structured feature, refactor, or delivery
  lifecycle.
license: MIT
metadata:
  phase: all
  category: orchestration
  version: "1.0.0"
---

# AI-DLC Workflow Runbook

The **AI-Driven Development Life Cycle (AI-DLC)** turns user intent into verified software through four structured stages (`Triage -> Inception -> Construction -> Operation`), spec-driven `.aidlc/` artifacts, adaptive depth, and configurable verification gates.

## Step 0: Load Governance Profile & Project State

1. Read `config/config.json` (or run `python3 scripts/tune.py show`) to verify:
   - Active `governance.mode` (`strict`, `balanced`, or `autonomous`)
   - Active `orchestration.protocol` (`hybrid`, `subagents`, `swarm`, or `workflow`)
   - Subagent caps (`max_nesting_depth`, `max_parallel_subagents`, `max_review_rounds`)
2. If `<project>/.aidlc/state.json` exists, inspect it with:
   `python3 scripts/state.py status --project <project>`
   Otherwise initialize a run:
   `python3 scripts/state.py init --project <project> --title "<title>" --intent "<intent>"`

See [phases-and-gates.md](references/phases-and-gates.md) for the complete governance matrix and rollback triggers.

## Step 1: Adaptive Depth Triage (`Triage`)

Classify scope using [intent-template.md](assets/intent-template.md) and lock the depth:

- **`fast-track`**: Isolated bug fix, documentation update, or 1–2 file cleanup with no API, schema, or security impact. Skips heavy Inception in `balanced` and `autonomous` modes (never skips Inception in `strict` mode).
- **`standard`**: Typical feature or multi-file change requiring requirements, design notes, unit breakdown, TDD, and peer review.
- **`deep`**: Greenfield service, breaking API/schema change, security-sensitive logic, or cross-cutting architecture requiring full DDD modeling, ADRs, and security sign-off.

Record the triage decision:
`python3 scripts/state.py triage --project <project> --depth <fast-track|standard|deep> --rationale "<why>"`

## Step 2: Inception (`researcher` + `architect`)

1. **Research Context**: Delegate read-only exploration to `researcher` (`invoke_subagent`) to map relevant modules, conventions, and test harnesses.
2. **Requirements Discovery**: Use `requirements-discovery` (`skills/requirements-discovery/SKILL.md`) and [requirements-template.md](assets/requirements-template.md) to write `<project>/.aidlc/inception/requirements.md` with Given/When/Then acceptance criteria.
3. **Architecture & DDD**: Use `architecture-ddd` (`skills/architecture-ddd/SKILL.md`) and [design-template.md](assets/design-template.md) to write `<project>/.aidlc/inception/design.md`. For `deep` runs, have `security` review the threat surface before coding.
4. **Unit Decomposition**: Use `task-decomposition` (`skills/task-decomposition/SKILL.md`) and [units-template.md](assets/units-template.md) to create disjoint-file work units and register every unit:
   `python3 scripts/state.py register-unit --project <project> --id U1 --title "..." --owner developer --files "src/a.py,tests/test_a.py" --skills "tdd-implementation"`
5. **Inception Gate**: Check `rules/gates.md`. Pause for human approval if `inception_to_construction` requires `human`, then advance:
   `python3 scripts/state.py advance --project <project> --to construction --approved-by <human|auto>`

## Step 3: Construction (`developer` + `verifier` + `security`)

Choose the execution topology matching unit count and `orchestration.protocol`:
- **Single unit / sequential**: Invoke `developer` via `invoke_subagent` using `tdd-implementation`.
- **Multiple disjoint units (parallel)**: Either launch a `swarm` board (`workspace: "share"` for authors + `verifier` peer), spawn parallel `developer` subagents in `share` workspaces, or run `workflows/pipeline.py` via `run_workflow`.

Mandatory verification loop before leaving Construction:
1. Author marks unit `in_review` (`state.py update-unit`) and records handoff `NEEDS_REVIEW` (`state.py record-handoff`).
2. `verifier` executes tests and `code-review` (`skills/code-review/SKILL.md`), writing [verification-report-template.md](assets/verification-report-template.md) to `<project>/.aidlc/construction/verification-report.md`.
3. For security-sensitive units (`deep` runs or auth/crypto/IO/infra changes), `security` runs `security-audit`.
4. If `CHANGES_REQUESTED`, peer-prompt the author directly via `send_message` (up to `max_review_rounds`, escalating to human if still failing).
5. Once all units are `approved`, advance the Construction gate:
   `python3 scripts/state.py advance --project <project> --to operation --approved-by <verifier|human>`

## Step 4: Operation (`operator`)

1. Invoke `operator` to run `release-operations` and `technical-documentation`, populating `<project>/.aidlc/operation/release-checklist.md` from [release-checklist-template.md](assets/release-checklist-template.md).
2. Present final diff summary, verified test output, and checklist to the user (pausing if `operation_to_completed` requires `human`).
3. Mark the workflow completed:
   `python3 scripts/state.py advance --project <project> --to completed --approved-by <human|auto>`
