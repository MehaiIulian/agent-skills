#!/usr/bin/env python3
"""Central AI-DLC manual tuning CLI for governance, orchestration, and agents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _frontmatter import (
    KEBAB_CASE_RE,
    RESERVED_AGENT_NAMES,
    TUNING_END_MARKER,
    TUNING_START_MARKER,
    VALID_ANTIGRAVITY_TOOLS,
    VALID_ANTIGRAVITY_TOOLS_SET,
    VALID_EXEC_POLICIES,
    VALID_EXEC_POLICIES_SET,
    VALID_MODELS,
    VALID_MODELS_SET,
    discover_skills,
    dump_frontmatter,
    parse_frontmatter,
    replace_managed_block,
)


def parse_bool_flag(raw: str) -> bool:
    val = raw.strip().lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError(f"Expected true/false boolean, got {raw!r}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def render_tuning_block(
    name: str, spec: dict[str, Any], cfg: dict[str, Any]
) -> str:
    gov = cfg["governance"]
    orch = cfg["orchestration"]
    mode = gov["mode"]
    status = "ENABLED" if spec["enabled"] else "DISABLED (mainAgent=false, subagent=false)"
    can_spawn = (
        spec["can_spawn_subagents"]
        and orch["allow_dynamic_subagents"]
        and spec["max_subagents"] > 0
        and any(t in spec["tools"] for t in ("define_subagent", "invoke_subagent"))
    )
    spawn_line = (
        f"Allowed (max {spec['max_subagents']} child subagents per turn/phase; "
        f"global nesting cap {orch['max_nesting_depth']}; "
        f"default child model `{orch['default_dynamic_subagent_model']}`)"
        if can_spawn
        else "Disabled (delegate upward or pass findings via `send_message`)"
    )

    lines = [
        "## Active Tuning Profile (Synced from `config/config.json`)",
        "",
        f"- **Agent**: `{name}`",
        f"- **Status**: {status}",
        f"- **Phase**: `{spec['phase']}`",
        f"- **Governance Mode**: `{mode}` (default depth: `{gov['default_depth']}`)",
        f"- **Orchestration Protocol**: `{orch['protocol']}`",
        f"- **Model Tier**: `{spec['model']}`",
        f"- **Execution Policy**: `{spec['commandExecutionPolicy']}`",
        f"- **Dynamic Subagent Spawning**: {spawn_line}",
        (
            f"- **Context Rotation Policy**: Rotate to a fresh subagent at "
            f"`{orch.get('context_rotation_threshold_pct', 50)}%` context "
            f"(or `>= {orch.get('max_steps_before_handoff', 25)}` tool steps); "
            f"fresh subagent per unit=`{'yes' if orch.get('fresh_subagent_per_unit', True) else 'no'}`; "
            f"distill handoffs to `<= {orch.get('handoff_max_tokens', 1500)}` tokens of context pointers "
            f"(recommend `/compact` on the primary chat thread)."
        ),
        "- **Bound Skills** (read `<repo>/skills/<skill>/SKILL.md` before executing):",
    ]
    if spec["skills"]:
        for skill in spec["skills"]:
            lines.append(f"  - `skills/{skill}/SKILL.md`")
    else:
        lines.append("  - _(none bound; load skills on demand as needed)_")

    lines.append("- **Custom Tuning Instructions**:")
    custom = spec.get("custom_instructions") or []
    if custom:
        for idx, item in enumerate(custom, 1):
            lines.append(f"  {idx}. {item}")
    else:
        lines.append("  - _(none)_")

    return "\n".join(lines)


def render_agent_document(
    name: str,
    spec: dict[str, Any],
    cfg: dict[str, Any],
    existing_text: str | None = None,
) -> str:
    fm: dict[str, Any] = {
        "name": name,
        "description": spec["description"],
        "model": spec["model"],
        "mainAgent": bool(spec["mainAgent"]) if spec["enabled"] else False,
        "subagent": bool(spec["subagent"]) if spec["enabled"] else False,
        "commandExecutionPolicy": spec["commandExecutionPolicy"],
        "tools": list(spec["tools"]),
        "skills": [f"skills/{s}" for s in spec["skills"]],
        "inheritMcp": bool(spec["inheritMcp"]),
        "inheritCustomizations": bool(spec["inheritCustomizations"]),
    }
    fm_text = dump_frontmatter(fm)
    tuning_inner = render_tuning_block(name, spec, cfg)

    if existing_text is None:
        body = (
            f"# {name}\n\n"
            f"## Mission\n\n"
            f"{spec['description']}\n\n"
            f"## Operating Protocol\n\n"
            f"1. Read and follow the `SKILL.md` runbook for each bound skill before acting.\n"
            f"2. Follow the active AI-DLC governance gates in `rules/gates.md`.\n"
            f"3. Exchange work via the Inter-Agent Handoff Envelope (`skills/subagent-orchestration/references/handoff-protocol.md`) using `send_message` or Swarm `@mentions`.\n"
        )
    else:
        _, body = parse_frontmatter(existing_text)

    updated_body = replace_managed_block(
        body, TUNING_START_MARKER, TUNING_END_MARKER, tuning_inner
    )
    if not updated_body.endswith("\n"):
        updated_body += "\n"
    return f"{fm_text}\n{updated_body.lstrip()}"


def render_gates_rule(cfg: dict[str, Any]) -> str:
    gov = cfg["governance"]
    orch = cfg["orchestration"]
    active_mode = gov["mode"]
    mode_cfg = gov["modes"][active_mode]
    gates = mode_cfg["gates"]

    fm = dump_frontmatter(
        {
            "trigger": "model_decision",
            "description": (
                "Active AI-DLC governance gates, adaptive depth triage criteria, "
                "and dynamic subagent orchestration limits. Apply whenever running an "
                "AI-DLC workflow, transitioning phases, or spawning subagents."
            ),
        }
    )

    lines = [
        "# AI-DLC Governance Gates & Orchestration Limits",
        "",
        "> Auto-synced from `config/config.json` by `python3 scripts/tune.py apply`. Do not hand-edit.",
        "",
        "## Active Governance Profile",
        "",
        f"- **Active Mode**: `{active_mode}` — {mode_cfg['description']}",
        f"- **Default Depth**: `{gov['default_depth']}`",
        f"- **Fast-Track Skips Inception**: `{'yes' if mode_cfg['allow_fast_track_skip_inception'] else 'no'}`",
        f"- **Orchestration Protocol**: `{orch['protocol']}`",
        "",
        "## Phase Gate Matrix",
        "",
        "| Transition | Required Approver (Active: `" + active_mode + "`) | Strict | Balanced | Autonomous |",
        "| :--- | :--- | :--- | :--- | :--- |",
        (
            f"| `inception -> construction` | **`{gates['inception_to_construction']}`** | "
            f"`{gov['modes']['strict']['gates']['inception_to_construction']}` | "
            f"`{gov['modes']['balanced']['gates']['inception_to_construction']}` | "
            f"`{gov['modes']['autonomous']['gates']['inception_to_construction']}` |"
        ),
        (
            f"| `construction -> operation` | **`{gates['construction_to_operation']}`** | "
            f"`{gov['modes']['strict']['gates']['construction_to_operation']}` | "
            f"`{gov['modes']['balanced']['gates']['construction_to_operation']}` | "
            f"`{gov['modes']['autonomous']['gates']['construction_to_operation']}` |"
        ),
        (
            f"| `operation -> completed` | **`{gates['operation_to_completed']}`** | "
            f"`{gov['modes']['strict']['gates']['operation_to_completed']}` | "
            f"`{gov['modes']['balanced']['gates']['operation_to_completed']}` | "
            f"`{gov['modes']['autonomous']['gates']['operation_to_completed']}` |"
        ),
        "",
        "Use `python3 scripts/state.py advance --project <dir> --to <phase> --approved-by <human|verifier|auto>` to enforce these gates.",
        "",
        "## Adaptive Depth Triage",
        "",
    ]

    for depth_name in ("fast-track", "standard", "deep"):
        d = gov["adaptive_depth"][depth_name]
        phases = " -> ".join(d["phases"])
        lines.append(f"- **`{depth_name}`** (`{phases}`): {d['criteria']}")

    lines.extend(
        [
            "",
            "## Dynamic Subagent & Verification Guardrails",
            "",
            f"- **Dynamic Subagent Creation (`define_subagent`)**: `{'enabled' if orch['allow_dynamic_subagents'] else 'disabled'}`",
            f"- **Max Nesting Depth**: `{orch['max_nesting_depth']}` (hard platform limit is 10)",
            f"- **Max Parallel Subagents**: `{orch['max_parallel_subagents']}`",
            f"- **Default Dynamic Subagent Model**: `{orch['default_dynamic_subagent_model']}`",
            f"- **Require Verifier For Code Changes**: `{'yes' if orch['require_verifier_for_code_changes'] else 'no'}`",
            f"- **Require Security Audit For Sensitive Changes**: `{'yes' if orch['require_security_audit_for_sensitive_changes'] else 'no'}`",
            f"- **Max Review Rounds**: `{orch['max_review_rounds']}` (escalate to human if unresolved)",
            f"- **Parallel Author Workspace Mode**: `{orch['workspace_isolation_for_parallel_authors']}`",
            "",
            "## Context Rotation & Fresh-Subagent Hygiene (Anti-Context-Rot)",
            "",
            f"- **Context Rotation Threshold**: `{orch.get('context_rotation_threshold_pct', 50)}%` of effective window (`~{orch.get('context_window_token_budget', 200000)}` token budget) or `>= {orch.get('max_steps_before_handoff', 25)}` tool steps",
            f"- **Fresh Subagent Per Unit & Review**: `{'enabled' if orch.get('fresh_subagent_per_unit', True) else 'disabled'}` (never recycle an older subagent across units `U1 -> U2`)",
            f"- **Distilled Handoff Budget**: `<= {orch.get('handoff_max_tokens', 1500)}` tokens using **context pointers** only (file paths, commits, `.aidlc/state.json`, next step — never copy raw tool logs into the new subagent)",
            "- **Primary Chat Thread**: Delegate heavy exploration/implementation to fresh subagents and recommend `/compact` when the main thread approaches the threshold.",
            "",
        ]
    )
    return f"{fm}\n" + "\n".join(lines)


def apply_config(
    repo_root: Path,
    cfg_path: Path | None = None,
    dry_run: bool = False,
    check: bool = False,
) -> tuple[bool, list[str]]:
    cfg_file = cfg_path or (repo_root / "config" / "config.json")
    cfg = load_json(cfg_file)
    changed: list[str] = []

    agents_dir = repo_root / "agents"
    for name, spec in cfg["agents"].items():
        agent_file = agents_dir / f"{name}.md"
        existing = agent_file.read_text(encoding="utf-8") if agent_file.is_file() else None
        rendered = render_agent_document(name, spec, cfg, existing_text=existing)
        if existing != rendered:
            rel = str(agent_file.relative_to(repo_root))
            changed.append(rel)
            if not dry_run and not check:
                agent_file.parent.mkdir(parents=True, exist_ok=True)
                agent_file.write_text(rendered, encoding="utf-8")

    gates_file = repo_root / "rules" / "gates.md"
    gates_existing = gates_file.read_text(encoding="utf-8") if gates_file.is_file() else None
    gates_rendered = render_gates_rule(cfg)
    if gates_existing != gates_rendered:
        rel = str(gates_file.relative_to(repo_root))
        changed.append(rel)
        if not dry_run and not check:
            gates_file.parent.mkdir(parents=True, exist_ok=True)
            gates_file.write_text(gates_rendered, encoding="utf-8")

    return len(changed) == 0, changed


def cmd_show(repo_root: Path, args: argparse.Namespace) -> int:
    cfg = load_json(repo_root / "config" / "config.json")
    gov = cfg["governance"]
    orch = cfg["orchestration"]
    mode = gov["mode"]
    gates = gov["modes"][mode]["gates"]

    print(f"AI-DLC Configuration ({repo_root / 'config' / 'config.json'})")
    print("=" * 72)
    print(f"Governance Mode : {mode} (default depth: {gov['default_depth']})")
    print(
        "Gate Approvers  : "
        f"inception->construction={gates['inception_to_construction']}, "
        f"construction->operation={gates['construction_to_operation']}, "
        f"operation->completed={gates['operation_to_completed']}"
    )
    print(
        f"Orchestration   : protocol={orch['protocol']}, "
        f"dynamic_subagents={orch['allow_dynamic_subagents']}, "
        f"max_depth={orch['max_nesting_depth']}, "
        f"max_parallel={orch['max_parallel_subagents']}, "
        f"default_child_model={orch['default_dynamic_subagent_model']}"
    )
    print(
        f"Verification    : require_verifier={orch['require_verifier_for_code_changes']}, "
        f"require_security={orch['require_security_audit_for_sensitive_changes']}, "
        f"max_review_rounds={orch['max_review_rounds']}, "
        f"author_workspace={orch['workspace_isolation_for_parallel_authors']}"
    )
    print(
        f"Context Guard   : rotate_at={orch.get('context_rotation_threshold_pct', 50)}%, "
        f"max_steps={orch.get('max_steps_before_handoff', 25)}, "
        f"fresh_per_unit={orch.get('fresh_subagent_per_unit', True)}, "
        f"handoff_max_tokens={orch.get('handoff_max_tokens', 1500)}"
    )
    print("\nAgents:")
    print("-" * 72)
    for name, spec in cfg["agents"].items():
        status = "ON" if spec["enabled"] else "OFF"
        roles = []
        if spec["mainAgent"]:
            roles.append("main")
        if spec["subagent"]:
            roles.append("sub")
        role_str = "/".join(roles) or "none"
        print(
            f"- {name} [{status}] phase={spec['phase']} model={spec['model']} "
            f"roles={role_str} policy={spec['commandExecutionPolicy']} "
            f"spawn={spec['can_spawn_subagents']}({spec['max_subagents']})"
        )
        print(f"    tools : {', '.join(spec['tools']) or '(none)'}")
        print(f"    skills: {', '.join(spec['skills']) or '(none)'}")
        if spec.get("custom_instructions"):
            print(f"    notes : {len(spec['custom_instructions'])} custom instruction(s)")
            for idx, inst in enumerate(spec["custom_instructions"], 1):
                print(f"      {idx}. {inst}")
    return 0


def cmd_set_mode(repo_root: Path, args: argparse.Namespace) -> int:
    cfg_path = repo_root / "config" / "config.json"
    cfg = load_json(cfg_path)
    cfg["governance"]["mode"] = args.mode
    if args.depth:
        cfg["governance"]["default_depth"] = args.depth
    save_json(cfg_path, cfg)
    _, changed = apply_config(repo_root)
    print(f"Set governance mode to '{args.mode}'. Synced {len(changed)} file(s).")
    return 0


def cmd_set_orchestration(repo_root: Path, args: argparse.Namespace) -> int:
    cfg_path = repo_root / "config" / "config.json"
    cfg = load_json(cfg_path)
    orch = cfg["orchestration"]
    if args.protocol is not None:
        orch["protocol"] = args.protocol
    if args.dynamic_subagents is not None:
        orch["allow_dynamic_subagents"] = args.dynamic_subagents
    if args.max_depth is not None:
        if not 1 <= args.max_depth <= 5:
            print("Error: --max-depth must be between 1 and 5.", file=sys.stderr)
            return 1
        orch["max_nesting_depth"] = args.max_depth
    if args.max_parallel is not None:
        if not 1 <= args.max_parallel <= 12:
            print("Error: --max-parallel must be between 1 and 12.", file=sys.stderr)
            return 1
        orch["max_parallel_subagents"] = args.max_parallel
    if args.default_model is not None:
        orch["default_dynamic_subagent_model"] = args.default_model
    if args.require_verifier is not None:
        orch["require_verifier_for_code_changes"] = args.require_verifier
    if args.require_security is not None:
        orch["require_security_audit_for_sensitive_changes"] = args.require_security
    if args.max_review_rounds is not None:
        if not 1 <= args.max_review_rounds <= 10:
            print("Error: --max-review-rounds must be between 1 and 10.", file=sys.stderr)
            return 1
        orch["max_review_rounds"] = args.max_review_rounds
    if args.workspace_isolation is not None:
        orch["workspace_isolation_for_parallel_authors"] = args.workspace_isolation
    if args.context_threshold_pct is not None:
        if not 20 <= args.context_threshold_pct <= 90:
            print("Error: --context-threshold-pct must be between 20 and 90.", file=sys.stderr)
            return 1
        orch["context_rotation_threshold_pct"] = args.context_threshold_pct
    if args.max_steps_handoff is not None:
        if not 5 <= args.max_steps_handoff <= 100:
            print("Error: --max-steps-handoff must be between 5 and 100.", file=sys.stderr)
            return 1
        orch["max_steps_before_handoff"] = args.max_steps_handoff
    if args.fresh_per_unit is not None:
        orch["fresh_subagent_per_unit"] = args.fresh_per_unit

    save_json(cfg_path, cfg)
    _, changed = apply_config(repo_root)
    print(f"Updated orchestration settings. Synced {len(changed)} file(s).")
    return 0


def cmd_tune_agent(repo_root: Path, args: argparse.Namespace) -> int:
    cfg_path = repo_root / "config" / "config.json"
    cfg = load_json(cfg_path)
    agents = cfg["agents"]
    if args.name not in agents:
        print(
            f"Error: unknown agent '{args.name}'. Known: {', '.join(sorted(agents))}",
            file=sys.stderr,
        )
        return 1

    spec = agents[args.name]
    known_skills = discover_skills(repo_root)

    if args.model is not None:
        spec["model"] = args.model
    if args.exec_policy is not None:
        spec["commandExecutionPolicy"] = args.exec_policy
    if args.main_agent is not None:
        spec["mainAgent"] = args.main_agent
    if args.subagent is not None:
        spec["subagent"] = args.subagent
    if args.enable:
        spec["enabled"] = True
    if args.disable:
        spec["enabled"] = False
    if args.can_spawn is not None:
        spec["can_spawn_subagents"] = args.can_spawn
    if args.max_subagents is not None:
        if not 0 <= args.max_subagents <= 12:
            print("Error: --max-subagents must be between 0 and 12.", file=sys.stderr)
            return 1
        spec["max_subagents"] = args.max_subagents
    if args.description is not None:
        if not args.description.strip():
            print("Error: --description cannot be empty.", file=sys.stderr)
            return 1
        spec["description"] = args.description.strip()

    for skill in args.add_skill:
        if skill not in known_skills:
            print(
                f"Error: skill '{skill}' not found under {repo_root / 'skills'}. "
                f"Available: {', '.join(sorted(known_skills))}",
                file=sys.stderr,
            )
            return 1
        if skill not in spec["skills"]:
            spec["skills"].append(skill)

    for skill in args.remove_skill:
        if skill in spec["skills"]:
            spec["skills"].remove(skill)

    for tool in args.add_tool:
        if tool not in VALID_ANTIGRAVITY_TOOLS_SET:
            print(
                f"Error: invalid Antigravity tool '{tool}'. "
                f"Allowed: {', '.join(VALID_ANTIGRAVITY_TOOLS)}",
                file=sys.stderr,
            )
            return 1
        if tool not in spec["tools"]:
            spec["tools"].append(tool)

    for tool in args.remove_tool:
        if tool in spec["tools"]:
            spec["tools"].remove(tool)

    if args.clear_instructions:
        spec["custom_instructions"] = []
    for inst in args.instruction:
        cleaned = inst.strip()
        if cleaned and cleaned not in spec["custom_instructions"]:
            spec["custom_instructions"].append(cleaned)

    save_json(cfg_path, cfg)
    _, changed = apply_config(repo_root)
    print(f"Tuned agent '{args.name}'. Synced {len(changed)} file(s).")
    return 0


def cmd_create_agent(repo_root: Path, args: argparse.Namespace) -> int:
    name = args.name.strip()
    if not KEBAB_CASE_RE.match(name):
        print(f"Error: agent name '{name}' must be lowercase kebab-case.", file=sys.stderr)
        return 1
    if name in RESERVED_AGENT_NAMES:
        print(f"Error: '{name}' collides with a built-in Antigravity agent.", file=sys.stderr)
        return 1

    cfg_path = repo_root / "config" / "config.json"
    cfg = load_json(cfg_path)
    if name in cfg["agents"]:
        print(f"Error: agent '{name}' already exists in config.", file=sys.stderr)
        return 1

    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else []
    known_skills = discover_skills(repo_root)
    for skill in skills:
        if skill not in known_skills:
            print(
                f"Error: skill '{skill}' not found under {repo_root / 'skills'}.",
                file=sys.stderr,
            )
            return 1

    tools = (
        [t.strip() for t in args.tools.split(",") if t.strip()]
        if args.tools
        else ["read_file", "send_message"]
    )
    for tool in tools:
        if tool not in VALID_ANTIGRAVITY_TOOLS_SET:
            print(
                f"Error: invalid tool '{tool}'. Allowed: {', '.join(VALID_ANTIGRAVITY_TOOLS)}",
                file=sys.stderr,
            )
            return 1

    cfg["agents"][name] = {
        "enabled": True,
        "phase": args.phase,
        "description": args.description.strip(),
        "model": args.model,
        "mainAgent": args.main_agent,
        "subagent": args.subagent,
        "commandExecutionPolicy": args.exec_policy,
        "inheritMcp": True,
        "inheritCustomizations": True,
        "tools": tools,
        "skills": skills,
        "can_spawn_subagents": args.can_spawn,
        "max_subagents": args.max_subagents,
        "custom_instructions": [],
    }
    save_json(cfg_path, cfg)
    _, changed = apply_config(repo_root)
    print(f"Created agent '{name}' and synced {len(changed)} file(s).")
    return 0


def cmd_apply(repo_root: Path, args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).resolve() if args.config else None
    in_sync, changed = apply_config(
        repo_root, cfg_path=cfg_path, dry_run=args.dry_run, check=args.check
    )
    if args.check:
        if not in_sync:
            print(
                "Out of sync with config/config.json: " + ", ".join(changed),
                file=sys.stderr,
            )
            return 1
        print("All agents and rules/gates.md are in sync.")
        return 0
    action = "Would update" if args.dry_run else "Synced"
    print(f"{action} {len(changed)} file(s)" + (f": {', '.join(changed)}" if changed else "."))
    return 0


def cmd_reset(repo_root: Path, args: argparse.Namespace) -> int:
    defaults_path = repo_root / "config" / "defaults.json"
    cfg_path = repo_root / "config" / "config.json"
    cfg_path.write_text(defaults_path.read_text(encoding="utf-8"), encoding="utf-8")
    _, changed = apply_config(repo_root)
    print(f"Reset config to defaults. Synced {len(changed)} file(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tune AI-DLC governance, orchestration limits, and specialist agents."
    )
    parser.add_argument(
        "--repo-root",
        default=str(SCRIPT_DIR.parent),
        help="Path to the agent-skills repository root.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="Show active AI-DLC config and agent roster.")

    p_mode = sub.add_parser("set-mode", help="Switch human verification gate mode.")
    p_mode.add_argument("mode", choices=["strict", "balanced", "autonomous"])
    p_mode.add_argument("--depth", choices=["auto", "fast-track", "standard", "deep"])

    p_orch = sub.add_parser("set-orchestration", help="Update orchestration settings.")
    p_orch.add_argument("--protocol", choices=["hybrid", "subagents", "swarm", "workflow"])
    p_orch.add_argument("--dynamic-subagents", type=parse_bool_flag)
    p_orch.add_argument("--max-depth", type=int)
    p_orch.add_argument("--max-parallel", type=int)
    p_orch.add_argument("--default-model", choices=list(VALID_MODELS))
    p_orch.add_argument("--require-verifier", type=parse_bool_flag)
    p_orch.add_argument("--require-security", type=parse_bool_flag)
    p_orch.add_argument("--max-review-rounds", type=int)
    p_orch.add_argument("--workspace-isolation", choices=["share", "branch"])
    p_orch.add_argument("--context-threshold-pct", type=int)
    p_orch.add_argument("--max-steps-handoff", type=int)
    p_orch.add_argument("--fresh-per-unit", type=parse_bool_flag)

    p_agent = sub.add_parser("tune-agent", help="Tune an individual agent.")
    p_agent.add_argument("name", help="Agent identifier (e.g. developer).")
    p_agent.add_argument("--model", choices=list(VALID_MODELS))
    p_agent.add_argument("--add-skill", action="append", default=[])
    p_agent.add_argument("--remove-skill", action="append", default=[])
    p_agent.add_argument("--add-tool", action="append", default=[])
    p_agent.add_argument("--remove-tool", action="append", default=[])
    p_agent.add_argument("--exec-policy", choices=list(VALID_EXEC_POLICIES))
    p_agent.add_argument("--main-agent", type=parse_bool_flag)
    p_agent.add_argument("--subagent", type=parse_bool_flag)
    enable_grp = p_agent.add_mutually_exclusive_group()
    enable_grp.add_argument("--enable", action="store_true")
    enable_grp.add_argument("--disable", action="store_true")
    p_agent.add_argument("--can-spawn", type=parse_bool_flag)
    p_agent.add_argument("--max-subagents", type=int)
    p_agent.add_argument("--instruction", action="append", default=[])
    p_agent.add_argument("--clear-instructions", action="store_true")
    p_agent.add_argument("--description")

    p_create = sub.add_parser("create-agent", help="Create a new specialist agent.")
    p_create.add_argument("name", help="New agent name (lowercase kebab-case).")
    p_create.add_argument("--description", required=True)
    p_create.add_argument(
        "--phase",
        default="construction",
        choices=["all", "inception", "construction", "operation"],
    )
    p_create.add_argument("--model", default="inherit", choices=list(VALID_MODELS))
    p_create.add_argument("--skills", default="")
    p_create.add_argument("--tools", default="read_file,send_message")
    p_create.add_argument("--main-agent", type=parse_bool_flag, default=False)
    p_create.add_argument("--subagent", type=parse_bool_flag, default=True)
    p_create.add_argument("--can-spawn", type=parse_bool_flag, default=False)
    p_create.add_argument("--max-subagents", type=int, default=0)
    p_create.add_argument(
        "--exec-policy", default="sandbox", choices=list(VALID_EXEC_POLICIES)
    )

    p_apply = sub.add_parser(
        "apply", help="Sync config/config.json to agents/*.md and rules/gates.md."
    )
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.add_argument("--check", action="store_true")
    p_apply.add_argument("--config")

    p_reset = sub.add_parser("reset", help="Reset config to config/defaults.json.")
    p_reset.add_argument("--force", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    handlers = {
        "show": cmd_show,
        "set-mode": cmd_set_mode,
        "set-orchestration": cmd_set_orchestration,
        "tune-agent": cmd_tune_agent,
        "create-agent": cmd_create_agent,
        "apply": cmd_apply,
        "reset": cmd_reset,
    }
    return handlers[args.command](repo_root, args)


if __name__ == "__main__":
    raise SystemExit(main())
