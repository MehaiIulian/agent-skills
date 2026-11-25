# Customization & Tuning Guide

## 1. Tuning Recipes (`scripts/tune.py`)

All tuning changes live in [config/config.json](../config/config.json) and propagate cleanly via `scripts/tune.py apply`:

- **Switch gate strictness**:
  ```bash
  python3 scripts/tune.py set-mode strict       # Human approval at every phase boundary
  python3 scripts/tune.py set-mode balanced     # Default: human Inception + Operation gates, verifier Construction gate
  python3 scripts/tune.py set-mode autonomous   # Verifier + auto gates; pauses only on blockers
  ```
- **Control dynamic subagent creation & concurrency**:
  ```bash
  python3 scripts/tune.py set-orchestration \
    --dynamic-subagents true \
    --max-depth 2 \
    --max-parallel 4 \
    --default-model flash
  ```
- **Adjust an agent's model, skills, tools, or persistent instructions**:
  ```bash
  python3 scripts/tune.py tune-agent architect --model pro --add-skill security-audit
  python3 scripts/tune.py tune-agent researcher --model flash_lite
  python3 scripts/tune.py tune-agent developer --instruction "Prefer table-driven unit tests."
  ```
- **Disable an agent without deleting it**:
  ```bash
  python3 scripts/tune.py tune-agent security --disable
  ```
  Disabling writes `mainAgent: false` and `subagent: false` into `agents/security.md` while keeping your config and prose intact. Re-enable later with `--enable`.

## 2. Enabling the Optional Lifecycle Hook (`hooks.json`)

[hooks.json](../hooks.json) defines `gate-guard` (disabled by default):
- **`SessionStart`**: Injects active `.aidlc/state.json` summary (phase, mode, depth, active units) into new conversations.
- **`PreToolUse` (`write_file|edit_file`)**: In `strict` mode while `phase == "inception"`, prompts confirmation (`{"decision": "ask"}`) before editing files outside `.aidlc/`.

To enable it, change `"enabled": false` to `"enabled": true` inside [hooks.json](../hooks.json) and run `python3 scripts/validate.py`.

## 3. Adding New Skills and Binding Them

1. Copy [skills/skill-authoring/assets/SKILL-template.md](../skills/skill-authoring/assets/SKILL-template.md) into `skills/<new-skill>/SKILL.md`.
2. Ensure YAML frontmatter `name` matches `<new-skill>` (lowercase kebab-case, 1–64 chars) and `description` explains both what it does and when to load it.
3. Bind it to any specialist agent:
   ```bash
   python3 scripts/tune.py tune-agent developer --add-skill <new-skill>
   ```
4. Validate: `python3 scripts/validate.py`.

## 4. Syncing to Other Tools (`scripts/install.py`)

Re-run `scripts/install.py` after customizing agents or adding skills when using `--method copy`:

```bash
python3 scripts/install.py claude-code --scope user
python3 scripts/install.py cursor --project /path/to/repo
python3 scripts/install.py codex --scope user
```

Use `--uninstall` with the same target/scope flags to cleanly remove installed files or Codex's managed `AGENTS.md` block.
