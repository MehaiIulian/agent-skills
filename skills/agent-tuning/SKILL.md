---
name: agent-tuning
description: >-
  Manually inspect, configure, and synchronize AI-DLC governance modes,
  adaptive depth defaults, orchestration limits, specialist agent models, tools,
  bound skills, and custom instructions. Use when the user asks to tune,
  enable, disable, customize, or create AI-DLC agents or gate behavior.
license: MIT
metadata:
  phase: all
  category: configuration
  version: "1.0.0"
---

# Manual Agent & AI-DLC Workflow Tuning

`config/config.json` is the single source of truth for AI-DLC behavior. Editing it through `scripts/tune.py` deterministically updates `agents/*.md` frontmatter + managed tuning blocks (`<!-- AIDLC:TUNING:START/END -->`) and `rules/gates.md` while preserving all hand-written agent prose.

## Step 1: Inspect Current Settings

```bash
python3 scripts/tune.py show
```

Review active governance mode, gate approvers, subagent nesting/concurrency caps, and each agent's `enabled` state, `model`, `tools`, `skills`, and `custom_instructions`.

## Step 2: Tune Governance & Orchestration

- **Switch human verification gate mode** (`strict`, `balanced`, or `autonomous`):
  ```bash
  python3 scripts/tune.py set-mode strict
  ```
- **Adjust orchestration protocol or subagent caps**:
  ```bash
  python3 scripts/tune.py set-orchestration \
    --protocol hybrid \
    --dynamic-subagents true \
    --max-depth 3 \
    --max-parallel 4 \
    --default-model inherit \
    --max-review-rounds 3
  ```

## Step 3: Tune Existing Specialist Agents

Modify model tiers, skills, native Antigravity tools, execution policy, spawn limits, or persistent tuning instructions:

```bash
python3 scripts/tune.py tune-agent developer \
  --model pro \
  --add-skill security-audit \
  --instruction "Always run typechecks alongside pytest before NEEDS_REVIEW."
```

Common tuning actions:
- Enable/disable an agent: `--enable` or `--disable` (disabling sets `mainAgent: false` and `subagent: false`).
- Toggle primary vs subagent visibility: `--main-agent true|false`, `--subagent true|false`.
- Clear or replace custom instructions: `--clear-instructions --instruction "..."`.
- Update execution policy: `--exec-policy off|auto|eager|sandbox`.

> **Guardrail**: `tune.py` validates every tool against the verified Antigravity 2.0 native tool set so misspelled tool names cannot hang subagents.

## Step 4: Create a New Persistent Specialist Agent

To promote a recurring role into a permanent specialist:

```bash
python3 scripts/tune.py create-agent perf-auditor \
  --description "Benchmarks hot paths and profiles memory/latency regressions." \
  --phase construction \
  --model pro \
  --skills code-review,systematic-debugging \
  --tools read_file,run_command,manage_task,send_message
```

## Step 5: Sync Check, Validate, or Reset

- Preview changes without writing: `python3 scripts/tune.py apply --dry-run`
- Verify zero drift between JSON config and Markdown files: `python3 scripts/tune.py apply --check`
- Validate the entire plugin after manual edits: `python3 scripts/validate.py`
- Restore factory defaults (`config/defaults.json`): `python3 scripts/tune.py reset`
