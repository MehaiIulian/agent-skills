---
trigger: model_decision
description: >-
  Active AI-DLC governance gates, adaptive depth triage criteria, and dynamic
  subagent orchestration limits. Apply whenever running an AI-DLC workflow,
  transitioning phases, or spawning subagents.
---

# AI-DLC Governance Gates & Orchestration Limits

> Auto-synced from `config/config.json` by `python3 scripts/tune.py apply`. Do not hand-edit.

## Active Governance Profile

- **Active Mode**: `balanced` — Human gate after Inception and before final Operation release; fast-track may skip full Inception for trivial low-risk changes (<= 2 files, no schema/API/security impact); verifier gate mandatory in Construction.
- **Default Depth**: `auto`
- **Fast-Track Skips Inception**: `yes`
- **Orchestration Protocol**: `hybrid`

## Phase Gate Matrix

| Transition | Required Approver (Active: `balanced`) | Strict | Balanced | Autonomous |
| :--- | :--- | :--- | :--- | :--- |
| `inception -> construction` | **`human`** | `human` | `human` | `auto` |
| `construction -> operation` | **`verifier`** | `human` | `verifier` | `verifier` |
| `operation -> completed` | **`human`** | `human` | `human` | `auto` |

Use `python3 scripts/state.py advance --project <dir> --to <phase> --approved-by <human|verifier|auto>` to enforce these gates.

## Adaptive Depth Triage

- **`fast-track`** (`triage -> construction -> operation`): Small bug fix, docs update, or isolated refactor touching 1-2 files with no API, schema, or security impact.
- **`standard`** (`triage -> inception -> construction -> operation`): Typical feature, enhancement, or multi-file fix requiring clear requirements, design notes, unit decomposition, TDD, and peer verification.
- **`deep`** (`triage -> inception -> construction -> operation`): Greenfield service, breaking API/schema migration, security-sensitive domain, or cross-cutting architecture requiring DDD modeling, ADRs, and dedicated security review.

## Dynamic Subagent & Verification Guardrails

- **Dynamic Subagent Creation (`define_subagent`)**: `enabled`
- **Max Nesting Depth**: `3` (hard platform limit is 10)
- **Max Parallel Subagents**: `4`
- **Default Dynamic Subagent Model**: `inherit`
- **Require Verifier For Code Changes**: `yes`
- **Require Security Audit For Sensitive Changes**: `yes`
- **Max Review Rounds**: `3` (escalate to human if unresolved)
- **Parallel Author Workspace Mode**: `share`

## Context Rotation & Fresh-Subagent Hygiene (Anti-Context-Rot)

- **Context Rotation Threshold**: `50%` of effective window (`~200000` token budget) or `>= 25` tool steps
- **Fresh Subagent Per Unit & Review**: `enabled` (never recycle an older subagent across units `U1 -> U2`)
- **Distilled Handoff Budget**: `<= 1500` tokens using **context pointers** only (file paths, commits, `.aidlc/state.json`, next step — never copy raw tool logs into the new subagent)
- **Primary Chat Thread**: Delegate heavy exploration/implementation to fresh subagents and recommend `/compact` when the main thread approaches the threshold.
