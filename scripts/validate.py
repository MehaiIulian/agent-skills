#!/usr/bin/env python3
"""Static and structural validator for the AI-DLC Agent Skills repository."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _frontmatter import (
    FrontmatterError,
    KEBAB_CASE_RE,
    RESERVED_AGENT_NAMES,
    TUNING_END_MARKER,
    TUNING_START_MARKER,
    VALID_ANTIGRAVITY_TOOLS_SET,
    VALID_EXEC_POLICIES_SET,
    VALID_MODELS_SET,
    discover_skills,
    parse_frontmatter,
)
from tune import apply_config

PLUGIN_ALLOWED_FIELDS = {
    "$schema",
    "name",
    "displayName",
    "description",
    "version",
    "disabled",
    "logo",
    "suggestedPrompts",
    "skills",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
FORBIDDEN_BRAND_PREFIXES = ("antigravity", "gemini", "claude", "cursor")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
RULE_MAX_BYTES = 24000


class Report:
    def __init__(self) -> None:
        self.findings: list[dict[str, str]] = []

    def error(self, file: str, message: str) -> None:
        self.findings.append({"severity": "error", "file": file, "message": message})

    def warning(self, file: str, message: str) -> None:
        self.findings.append({"severity": "warning", "file": file, "message": message})

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f["severity"] == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f["severity"] == "warning")


def validate_plugin(repo_root: Path, report: Report) -> None:
    p = repo_root / "plugin.json"
    if not p.is_file():
        report.error("plugin.json", "Missing required plugin.json manifest.")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error("plugin.json", f"Invalid JSON: {exc}")
        return
    if not isinstance(data, dict):
        report.error("plugin.json", "plugin.json root must be a JSON object.")
        return

    unknown = sorted(set(data.keys()) - PLUGIN_ALLOWED_FIELDS)
    if unknown:
        report.error("plugin.json", f"Disallowed top-level fields: {', '.join(unknown)}")

    name = data.get("name")
    if not isinstance(name, str) or not KEBAB_CASE_RE.match(name):
        report.error("plugin.json", "Field 'name' must be a non-empty lowercase kebab-case string.")
    elif name.lower().startswith(FORBIDDEN_BRAND_PREFIXES):
        report.warning("plugin.json", f"Plugin 'name' ({name}) should not start with a platform brand prefix.")

    display = data.get("displayName", "")
    if isinstance(display, str) and display.lower().startswith(FORBIDDEN_BRAND_PREFIXES):
        report.warning("plugin.json", f"Plugin 'displayName' ({display}) should not start with a platform brand prefix.")

    prompts = data.get("suggestedPrompts")
    if prompts is not None:
        if not isinstance(prompts, list) or len(prompts) > 3:
            report.error("plugin.json", "'suggestedPrompts' must be a list of at most 3 strings.")
        elif any(not isinstance(item, str) or not item.strip() for item in prompts):
            report.error("plugin.json", "Every entry in 'suggestedPrompts' must be a non-empty string.")

    logo = data.get("logo")
    if logo is not None:
        if not isinstance(logo, str) or logo.startswith("/") or "://" in logo:
            report.error("plugin.json", "'logo' must be a relative file path inside the plugin.")
        elif not (repo_root / logo).is_file():
            report.error("plugin.json", f"Logo file does not exist: {logo}")

    repo = data.get("repository")
    if repo is not None and not isinstance(repo, str):
        report.error("plugin.json", "'repository' must be a URL string in Antigravity plugin.json schema.")


def validate_skills(repo_root: Path, report: Report) -> set[str]:
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        report.error("skills", "Missing skills/ directory.")
        return set()

    found_skills: set[str] = set()
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        rel_dir = f"skills/{entry.name}"
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            report.error(rel_dir, "Skill directory missing SKILL.md (must be one level deep).")
            continue

        rel_file = f"{rel_dir}/SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        try:
            fm, body = parse_frontmatter(text)
        except FrontmatterError as exc:
            report.error(rel_file, f"Frontmatter parse error: {exc}")
            continue
        if not fm:
            report.error(rel_file, "Missing YAML frontmatter.")
            continue

        s_name = fm.get("name")
        if not isinstance(s_name, str) or not KEBAB_CASE_RE.match(s_name) or len(s_name) > 64:
            report.error(rel_file, "Frontmatter 'name' must be 1..64 char lowercase kebab-case.")
        elif s_name != entry.name:
            report.error(rel_file, f"Frontmatter 'name' ({s_name}) must match folder name ({entry.name}).")
        else:
            found_skills.add(s_name)

        desc = fm.get("description")
        if not isinstance(desc, str) or not desc.strip() or len(desc) > 1024:
            report.error(rel_file, "Frontmatter 'description' must be non-empty and <= 1024 characters.")

        stripped_body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
        stripped_body = re.sub(r"`+[^`\n]+`+", "", stripped_body)
        for match in MD_LINK_RE.finditer(stripped_body):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            link_path = target.split("#", 1)[0]
            if link_path.startswith(("references/", "assets/", "scripts/", "examples/", "./")):
                resolved = (entry / link_path).resolve()
                if not resolved.exists():
                    report.error(rel_file, f"Broken relative skill link: {target}")

    return found_skills


def validate_agents_and_config(
    repo_root: Path, known_skills: set[str], report: Report
) -> None:
    cfg_path = repo_root / "config" / "config.json"
    defaults_path = repo_root / "config" / "defaults.json"
    schema_path = repo_root / "config" / "config.schema.json"

    for p in (schema_path, defaults_path, cfg_path):
        rel = str(p.relative_to(repo_root))
        if not p.is_file():
            report.error(rel, f"Missing required config file: {rel}")
            return
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.error(rel, f"Invalid JSON: {exc}")
            return

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    gov = cfg.get("governance", {})
    if gov.get("mode") not in ("strict", "balanced", "autonomous"):
        report.error("config/config.json", f"Invalid governance.mode: {gov.get('mode')!r}")

    orch = cfg.get("orchestration", {})
    depth = orch.get("max_nesting_depth")
    if not isinstance(depth, int) or not (1 <= depth <= 5):
        report.error("config/config.json", "orchestration.max_nesting_depth must be an integer in [1, 5].")
    ctx_pct = orch.get("context_rotation_threshold_pct")
    if not isinstance(ctx_pct, int) or not (20 <= ctx_pct <= 90):
        report.error("config/config.json", "orchestration.context_rotation_threshold_pct must be an integer in [20, 90].")
    max_steps = orch.get("max_steps_before_handoff")
    if not isinstance(max_steps, int) or not (5 <= max_steps <= 100):
        report.error("config/config.json", "orchestration.max_steps_before_handoff must be an integer in [5, 100].")

    cfg_agents = cfg.get("agents", {})
    if not isinstance(cfg_agents, dict) or not cfg_agents:
        report.error("config/config.json", "config.agents must be a non-empty object.")
        return

    for agent_name, spec in cfg_agents.items():
        if agent_name in RESERVED_AGENT_NAMES:
            report.error("config/config.json", f"Agent name '{agent_name}' collides with reserved built-in.")
        if spec.get("model") not in VALID_MODELS_SET:
            report.error("config/config.json", f"Agent '{agent_name}' has invalid model: {spec.get('model')!r}")
        if spec.get("commandExecutionPolicy") not in VALID_EXEC_POLICIES_SET:
            report.error("config/config.json", f"Agent '{agent_name}' has invalid commandExecutionPolicy.")
        for t in spec.get("tools", []):
            if t not in VALID_ANTIGRAVITY_TOOLS_SET:
                report.error("config/config.json", f"Agent '{agent_name}' lists unknown tool: {t!r}")
        for s in spec.get("skills", []):
            if s not in known_skills:
                report.error("config/config.json", f"Agent '{agent_name}' references missing skill: {s!r}")

    agents_dir = repo_root / "agents"
    if not agents_dir.is_dir():
        report.error("agents", "Missing agents/ directory.")
        return

    disk_agents = {p.stem: p for p in agents_dir.glob("*.md")}
    for missing in sorted(set(cfg_agents.keys()) - set(disk_agents.keys())):
        report.error(f"agents/{missing}.md", f"Agent '{missing}' defined in config but missing agents/{missing}.md.")
    for extra in sorted(set(disk_agents.keys()) - set(cfg_agents.keys())):
        report.error(f"agents/{extra}.md", f"Agent file agents/{extra}.md is not registered in config/config.json.")

    for stem, agent_path in sorted(disk_agents.items()):
        rel = f"agents/{agent_path.name}"
        raw = agent_path.read_text(encoding="utf-8")
        try:
            fm, _ = parse_frontmatter(raw)
        except FrontmatterError as exc:
            report.error(rel, f"Frontmatter parse error: {exc}")
            continue
        if not fm:
            report.error(rel, "Missing YAML frontmatter.")
            continue
        if fm.get("name") != stem:
            report.error(rel, f"Frontmatter 'name' ({fm.get('name')!r}) must match filename stem ({stem!r}).")
        if stem in RESERVED_AGENT_NAMES:
            report.error(rel, f"Agent '{stem}' collides with built-in Antigravity agent name.")
        if not str(fm.get("description", "")).strip():
            report.error(rel, "Frontmatter 'description' must be non-empty.")
        if fm.get("model") not in VALID_MODELS_SET:
            report.error(rel, f"Invalid model: {fm.get('model')!r}")
        if fm.get("commandExecutionPolicy") not in VALID_EXEC_POLICIES_SET:
            report.error(rel, f"Invalid commandExecutionPolicy: {fm.get('commandExecutionPolicy')!r}")
        for tool in fm.get("tools", []):
            if tool not in VALID_ANTIGRAVITY_TOOLS_SET:
                report.error(rel, f"Unmapped or invalid Antigravity tool: {tool!r}")
        for skill_ref in fm.get("skills", []):
            if not isinstance(skill_ref, str) or not skill_ref.startswith("skills/"):
                report.error(rel, f"Skill reference must look like 'skills/<name>': {skill_ref!r}")
            else:
                skill_name = skill_ref.split("/", 1)[1]
                if skill_name not in known_skills:
                    report.error(rel, f"Referenced skill does not exist: {skill_ref}")
        if TUNING_START_MARKER not in raw or TUNING_END_MARKER not in raw:
            report.error(rel, "Missing managed tuning markers (<!-- AIDLC:TUNING:START/END -->).")

    in_sync, changed = apply_config(repo_root, check=True)
    if not in_sync:
        report.error(
            "config/config.json",
            f"Config drift detected; run 'python3 scripts/tune.py apply'. Out of sync: {', '.join(changed)}",
        )


def validate_rules(repo_root: Path, report: Report) -> None:
    rules_dir = repo_root / "rules"
    if not rules_dir.is_dir():
        report.error("rules", "Missing rules/ directory.")
        return

    for rule_file in sorted(rules_dir.glob("*.md")):
        rel = f"rules/{rule_file.name}"
        raw = rule_file.read_text(encoding="utf-8")
        size = len(raw.encode("utf-8"))
        if size >= RULE_MAX_BYTES:
            report.error(rel, f"Rule file exceeds 24,000 byte limit ({size} bytes).")
        try:
            fm, _ = parse_frontmatter(raw)
        except FrontmatterError as exc:
            report.error(rel, f"Frontmatter parse error: {exc}")
            continue

        if rule_file.name in ("AGENTS.md", "GEMINI.md"):
            if fm is not None:
                report.error(rel, f"{rule_file.name} must not have YAML frontmatter.")
            continue

        if not fm:
            report.error(rel, "Named rule files must specify YAML frontmatter with 'trigger'.")
            continue
        trigger = fm.get("trigger")
        if trigger not in ("always_on", "model_decision", "glob", "manual"):
            report.error(rel, f"Invalid rule trigger: {trigger!r}")
        if trigger == "model_decision" and not str(fm.get("description", "")).strip():
            report.error(rel, "Rule with trigger 'model_decision' requires a non-empty 'description'.")
        if trigger == "glob" and not isinstance(fm.get("globs"), str):
            report.error(rel, "Rule with trigger 'glob' must specify 'globs' as a comma-separated string.")


def validate_hooks(repo_root: Path, report: Report) -> None:
    hooks_file = repo_root / "hooks.json"
    if not hooks_file.is_file():
        report.error("hooks.json", "Missing hooks.json.")
        return
    try:
        data = json.loads(hooks_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.error("hooks.json", f"Invalid JSON: {exc}")
        return
    if not isinstance(data, dict) or not data:
        report.error("hooks.json", "hooks.json must be a non-empty object keyed by hook name.")
        return

    flat_events = {"SessionStart", "PreInvocation", "PostInvocation", "Stop"}
    grouped_events = {"PreToolUse", "PostToolUse"}

    def _check_handler(hook_name: str, h: Any) -> None:
        if not isinstance(h, dict) or not isinstance(h.get("command"), str):
            report.error("hooks.json", f"Hook '{hook_name}' has invalid handler entry.")
            return
        for token in h["command"].split():
            if token.startswith("./"):
                target = (repo_root / token[2:]).resolve()
                if not target.is_file():
                    report.error("hooks.json", f"Hook script not found: {token}")
                elif not os.access(target, os.X_OK):
                    report.error("hooks.json", f"Hook script is not executable (0755): {token}")

    for hook_name, spec in data.items():
        if not isinstance(spec, dict):
            report.error("hooks.json", f"Hook '{hook_name}' must map to an object.")
            continue
        for ev in flat_events:
            if ev in spec:
                if not isinstance(spec[ev], list):
                    report.error("hooks.json", f"{hook_name}.{ev} must be a flat handler list.")
                else:
                    for h in spec[ev]:
                        _check_handler(hook_name, h)
        for ev in grouped_events:
            if ev in spec:
                if not isinstance(spec[ev], list):
                    report.error("hooks.json", f"{hook_name}.{ev} must be a grouped matcher list.")
                else:
                    for grp in spec[ev]:
                        if not isinstance(grp, dict) or "matcher" not in grp or not isinstance(grp.get("hooks"), list):
                            report.error("hooks.json", f"{hook_name}.{ev} items require 'matcher' and 'hooks' list.")
                        else:
                            for h in grp["hooks"]:
                                _check_handler(hook_name, h)


def validate_python_files(repo_root: Path, report: Report) -> None:
    scripts_dir = repo_root / "scripts"
    if scripts_dir.is_dir():
        for py in sorted(scripts_dir.rglob("*.py")):
            rel = str(py.relative_to(repo_root))
            src = py.read_text(encoding="utf-8")
            try:
                ast.parse(src, filename=rel)
            except SyntaxError as exc:
                report.error(rel, f"Python syntax error: {exc}")
            if not py.name.startswith("_") and not os.access(py, os.X_OK):
                report.error(rel, f"CLI/hook script missing executable permission (+x): {rel}")

    workflows_dir = repo_root / "workflows"
    if workflows_dir.is_dir():
        for py in sorted(workflows_dir.rglob("*.py")):
            rel = str(py.relative_to(repo_root))
            src = py.read_text(encoding="utf-8")
            try:
                compile(src, rel, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            except SyntaxError as exc:
                report.error(rel, f"Workflow script syntax error: {exc}")


def run_validation(repo_root: Path) -> Report:
    report = Report()
    validate_plugin(repo_root, report)
    known_skills = validate_skills(repo_root, report)
    validate_agents_and_config(repo_root, known_skills, report)
    validate_rules(repo_root, report)
    validate_hooks(repo_root, report)
    validate_python_files(repo_root, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate plugin manifest, skills, agents, rules, hooks, configs, and scripts."
    )
    parser.add_argument(
        "--repo-root",
        default=str(SCRIPT_DIR.parent),
        help="Path to repository root.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON validation report.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    report = run_validation(repo_root)

    if args.json:
        print(
            json.dumps(
                {
                    "errors": report.error_count,
                    "warnings": report.warning_count,
                    "findings": report.findings,
                },
                indent=2,
            )
        )
    else:
        skill_count = len(discover_skills(repo_root))
        agent_count = len(list((repo_root / "agents").glob("*.md"))) if (repo_root / "agents").is_dir() else 0
        print(
            f"Validation summary: {skill_count} skill(s), {agent_count} agent(s) | "
            f"{report.error_count} error(s), {report.warning_count} warning(s)"
        )
        for f in report.findings:
            print(f"  [{f['severity'].upper()}] {f['file']}: {f['message']}")

    return 1 if report.error_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
