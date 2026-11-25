---
name: skill-authoring
description: >-
  Create, structure, bind, and validate new Agent Skills (SKILL.md) conforming
  to both Google Antigravity and the open agentskills.io specification. Use when
  adding new development skills to the repository or updating existing ones.
license: MIT
metadata:
  phase: all
  category: meta
  version: "1.0.0"
---

# Authoring Portable Agent Skills

Skills in this repository follow both **Google Antigravity** plugin discovery and the open **`agentskills.io`** specification so one `SKILL.md` works across Antigravity, Claude Code, Cursor, and Codex.

## Step 1: Choose Name & Directory Layout

Every skill MUST sit **one level deep** at `skills/<skill-name>/SKILL.md`:

```text
skills/<skill-name>/
├── SKILL.md          # Required: YAML frontmatter + concise runbook
├── references/       # Optional: detailed checklists/specs read on demand
├── assets/           # Optional: templates or starter files
└── scripts/          # Optional: executable helpers (chmod 0755)
```

Naming rules:
- Lowercase letters, numbers, and single hyphens only (`^[a-z0-9]+(-[a-z0-9]+)*$`), 1–64 chars.
- Frontmatter `name` MUST exactly match the parent directory `<skill-name>`.

## Step 2: Draft `SKILL.md` Using Progressive Disclosure

Start from [assets/SKILL-template.md](assets/SKILL-template.md):
1. **`description` (<= 1024 chars)**: Write in third person stating **what** it does AND **when** an agent should load it. This is the only metadata loaded into context until activated.
2. **Concise Actionable Body**: Focus on non-obvious procedures, inputs/outputs, verification commands, and handoff contracts—omit generic coding advice the model already knows.
3. **Offload Bulk**: Move long checklists or templates into `references/` or `assets/` and link them via relative Markdown paths (for example `[checklist](references/checklist.md)` or [template](assets/SKILL-template.md)).

## Step 3: Bind to Specialist Agents (Optional)

Bind the new skill to one or more agents in `config/config.json`:

```bash
python3 scripts/tune.py tune-agent developer --add-skill <skill-name>
```

## Step 4: Validate & Sync Cross-Tool Targets

1. Run static validation (checks frontmatter, relative links, config sync, and rules):
   `python3 scripts/validate.py`
2. If already installed to other tools in `copy` mode, re-run `python3 scripts/install.py <target>` to push the new skill.
