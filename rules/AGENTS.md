# AI-DLC Agent Skills Suite

This workspace has the **AI-DLC Agent Skills** plugin active, implementing the **AI-Driven Development Life Cycle (AI-DLC)** with tunable specialist agents, portable `SKILL.md` runbooks, and hybrid multi-agent orchestration.

## Core Operating Principles

1. **AI Proposes, Humans Validate at Configured Gates**: Propose specs, architecture, units, and verified code — pause for human confirmation at the gate points defined by the active governance mode (`strict`, `balanced`, or `autonomous`) in `config/config.json`.
2. **Adaptive Depth First**: Never force heavyweight Inception ceremonies onto a 1-file fix, and never skip architecture/security design on risky or cross-cutting changes. Triage tasks into `fast-track`, `standard`, or `deep` before acting.
3. **Load Skills Before Acting**: Read the relevant `skills/<skill-name>/SKILL.md` file whenever a phase or engineering task matches its description (`workflow`, `subagent-orchestration`, `agent-tuning`, `tdd-implementation`, `code-review`, `security-audit`, etc.).
4. **Structured Handoffs & Disjoint Ownership**: Track active runs in `.aidlc/state.json` via `scripts/state.py`, assign disjoint file ownership to parallel authors, and exchange work via the Inter-Agent Handoff Envelope (`send_message` or Swarm `@mentions`).
5. **Respect Manual Tuning & Subagent Caps**: Follow `config/config.json` and `rules/gates.md` for model tiers, tool allowlists, `max_nesting_depth`, and `max_parallel_subagents`. Use `python3 scripts/tune.py` to tune settings cleanly.
6. **50% Context Rotation & Fresh Subagents (Anti-Context-Rot)**: Spawn a fresh subagent per Unit of Work and per verification round (`fresh_subagent_per_unit: true`). Whenever an agent approaches **50% context utilization** (or `>= 25` tool steps / a `gate_guard` rotation alert), stop deep work, distill state into a compact Context-Pointer Handoff (`<= 1,500` tokens, no raw logs) in `.aidlc/handoffs/`, and spawn a fresh replacement subagent (or recommend `/compact` on the primary chat thread).
