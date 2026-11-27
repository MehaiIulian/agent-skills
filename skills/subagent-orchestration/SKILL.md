---
name: subagent-orchestration
description: >-
  Spawn pre-defined or dynamic subagents, pass skill instructions, route
  structured prompts and handoffs between agents, and coordinate Swarm boards
  or dynamic run_workflow pipelines. Use when delegating specialized work,
  creating bespoke subagents automatically, or running multi-agent peer reviews.
license: MIT
metadata:
  phase: all
  category: orchestration
  version: "1.0.0"
---

# Subagent Orchestration & Inter-Agent Prompting

Agents collaborate through a **hybrid orchestration model**: pre-defined specialist agents, dynamically created subagents (`define_subagent`), direct peer prompting (`send_message`), shared Swarm boards (`swarm`), and scripted workflows (`run_workflow`).

## 1. Check Configured Guardrails First

Before spawning children, verify `config/config.json`:
- `orchestration.allow_dynamic_subagents` (must be `true` to call `define_subagent`)
- `orchestration.max_nesting_depth` (default `3`, strictly below the platform ceiling of 10)
- `orchestration.max_parallel_subagents` (default `4`)
- `orchestration.default_dynamic_subagent_model` (default `inherit`)
- Agent-specific `can_spawn_subagents` and `max_subagents`

## 2. Mode A — Pre-Defined Specialists (`invoke_subagent`)

Prefer tuned specialist agents from `agents/` whenever a role matches:
- `researcher` (`inherit` workspace, read-only context mapping)
- `architect` (Inception specs, DDD, unit design)
- `developer` (Construction unit implementation)
- `verifier` (`inherit` workspace, independent testing and review)
- `security` (`inherit` workspace, threat modeling and security review)
- `operator` (release checklist, docs, postmortem)

Always specify in the prompt:
1. Exact unit/scope and files owned (and files **not** to touch).
2. Which `skills/<skill-name>/SKILL.md` files to read first.
3. Exact completion condition and peer/parent `conversationId` or target to notify.

## 3. Mode B — Automatic Dynamic Subagent Creation (`define_subagent`)

When no existing specialist fits (e.g., schema migration, benchmark profiling, API contract auditing):
1. Call `define_subagent` with:
   - `Name`: lowercase kebab-case role name not colliding with existing or built-in names (`self`, `browser`, `research`, `deepagent`, `review-agent`, `image-generator`).
   - `Description`: crisp trigger summary.
   - `EnableWriteTools`: `true` ONLY for authors/fixers; keep `false` for readers, auditors, and reviewers.
   - `EnableSubagentTools`: `false` unless nesting is explicitly needed and depth `< max_nesting_depth`.
   - `SystemPrompt`: role boundaries, required `SKILL.md` files to read, and output contract (see [dynamic-subagent-templates.md](references/dynamic-subagent-templates.md)).
2. Immediately launch with `invoke_subagent`, passing `Model: "inherit"` (or `default_dynamic_subagent_model`) and `Workspace: "share"` if editing alongside other authors (or `"inherit"` for read-only work).
3. Include the target peer's `conversationId` or instruct the child to return a structured Handoff Envelope.

## 4. Mode C — Inter-Agent Prompting (`send_message`) & Peer Handoffs

Agents communicate cleanly without flooding parent context by following [handoff-protocol.md](references/handoff-protocol.md):
- Pass **conversationIds** explicitly when two peer subagents should iterate directly (e.g., `developer` <-> `verifier`).
- Every handoff uses the standard **Handoff Envelope** (`status`, `unit`, `skills_used`, `artifacts`, `findings`/`summary`, `next_action`).
- Record significant phase/unit transitions in `.aidlc/handoffs/` via `scripts/state.py record-handoff` when running in an agent with `run_command` (design-only or read-only agents without `run_command`, such as `architect` or `researcher`, write a `.aidlc/handoffs/` Markdown note or return the Handoff Envelope to `orchestrator` to record):
  `python3 scripts/state.py record-handoff --project <dir> --from <src> --to <dst> --phase <phase> --status <STATUS> --summary "..."`

## 5. Mode D — Parallel Swarm Board (`swarm`) & Pipelines (`run_workflow`)

- **Swarm (`swarm`)**: Use when 3+ disjoint work units or independent review tracks run concurrently. Create named workers (`u1-dev`, `u2-dev`, `verifier`, `security`) with `workspace: "share"` for authors and `inherit` for verifiers. Instruct peers to `@mention` only the next actor (never CC `@coordinator` until `[done]` or blocked) and refer to earlier reports by board sequence number (`#4`).
- **Dynamic Workflow (`run_workflow`)**: Run `workflows/pipeline.py` when deterministic Inception -> parallel Construction -> Verifier/Security loop -> Operation orchestration in Python is preferred.

## 6. 50% Context Rotation & Fresh-Subagent Protocol (Anti-Context-Rot)

To prevent *Context Rot* (attention dilution and lost middle constraints above ~50% context):
1. **Fresh Subagent Per Unit & Review (`fresh_subagent_per_unit: true`)**: Spawn a brand-new subagent (`invoke_subagent`) for each Unit of Work (`U1`, `U2`, ...) and each independent review pass rather than recycling long-running subagents.
2. **Rotate at ~50% Context (or `>= max_steps_before_handoff` Tool Steps)**: When approaching `orchestration.context_rotation_threshold_pct` (default `50%`) or `orchestration.max_steps_before_handoff` (default `25` tool steps), or when `gate_guard.py` injects `[CONTEXT ROTATION GUARD]`:
   - Stop starting new exploration or edits in the current context.
   - Write a compact **Context-Pointer Handoff** (`<= 1,500` tokens) via `scripts/state.py record-handoff` (or via `write_file` in `.aidlc/handoffs/` / `send_message` to `orchestrator` when running in an agent without `run_command`, such as `architect` or `researcher`) containing ONLY: completed items, exact file paths/commits, current test status, open blockers, required `SKILL.md` paths, and the exact next step (**never** copy-paste raw terminal logs or full file dumps).
   - Spawn a fresh replacement subagent (`invoke_subagent`) initialized strictly with that handoff pointer so it starts at 0% context.
3. **Primary Chat Thread**: Keep the root conversation lean by delegating heavy exploration/implementation to fresh subagents, and recommend `/compact` to the user when the primary chat thread grows large.
