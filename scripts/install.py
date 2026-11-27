#!/usr/bin/env python3
"""Cross-tool installer and exporter for AI-DLC Agent Skills."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _frontmatter import (
    CODEX_END_MARKER,
    CODEX_START_MARKER,
    dump_frontmatter,
    parse_frontmatter,
    remove_managed_block,
    replace_managed_block,
)

PLUGIN_NAME = "agent-skills"
PLUGIN_IGNORED_ENTRIES = {".git", "__pycache__", ".aidlc", "tests", ".pytest_cache"}

CLAUDE_TOOL_MAP: dict[str, list[str]] = {
    "read_file": ["Read", "Glob", "Grep"],
    "edit_file": ["Edit"],
    "write_file": ["Write"],
    "run_command": ["Bash"],
    "manage_task": ["Bash"],
    "search_web": ["WebSearch"],
    "ask_question": ["AskUserQuestion"],
    "define_subagent": ["Agent"],
    "invoke_subagent": ["Agent"],
}


def _copy_filtered_tree(src: Path, dst: Path) -> None:
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(*PLUGIN_IGNORED_ENTRIES, "*.pyc"),
    )


def _install_dir_entry(
    src: Path, dst: Path, method: str, dry_run: bool, force: bool
) -> str:
    if dry_run:
        return f"[dry-run] {method} {src} -> {dst}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        if not force:
            # Always safe to replace an existing install of our own directory
            if dst.is_symlink() or dst.is_file():
                dst.unlink()
            else:
                shutil.rmtree(dst)
        else:
            if dst.is_symlink() or dst.is_file():
                dst.unlink()
            else:
                shutil.rmtree(dst)
    if method == "symlink":
        os.symlink(src, dst)
    else:
        if (src / "plugin.json").is_file():
            _copy_filtered_tree(src, dst)
        else:
            shutil.copytree(
                src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
    return f"{method}: {dst}"


def _remove_path(path: Path, dry_run: bool) -> str | None:
    if not (path.exists() or path.is_symlink()):
        return None
    if dry_run:
        return f"[dry-run] remove {path}"
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)
    return f"removed: {path}"


def _iter_skills(repo_root: Path) -> list[Path]:
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        p for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
    )


def _iter_enabled_agents(repo_root: Path) -> list[tuple[Path, dict[str, Any], str]]:
    agents_dir = repo_root / "agents"
    if not agents_dir.is_dir():
        return []
    out: list[tuple[Path, dict[str, Any], str]] = []
    for agent_file in sorted(agents_dir.glob("*.md")):
        fm, body = parse_frontmatter(agent_file.read_text(encoding="utf-8"))
        if not fm:
            continue
        if fm.get("mainAgent") is False and fm.get("subagent") is False:
            continue
        out.append((agent_file, fm, body))
    return out


def install_antigravity(
    repo_root: Path,
    scope: str,
    project: Path | None,
    target_dir: Path | None,
    method: str,
    dry_run: bool,
    uninstall: bool,
    force: bool,
) -> list[str]:
    if target_dir is not None:
        base = target_dir
    elif scope == "user":
        base = Path.home() / ".gemini" / "config" / "plugins"
    else:
        if project is None:
            raise ValueError("--project is required for project scope.")
        base = project / ".agents" / "plugins"

    plugin_dst = base / PLUGIN_NAME
    if uninstall:
        res = _remove_path(plugin_dst, dry_run)
        return [res] if res else [f"not installed: {plugin_dst}"]

    msg = _install_dir_entry(repo_root, plugin_dst, method, dry_run, force)
    return [
        msg,
        f"Antigravity link: [AI-DLC Agent Skills](customization://{PLUGIN_NAME})",
    ]


def _translate_claude_tools(tools: list[Any]) -> list[str]:
    mapped: list[str] = []
    for t in tools:
        for ct in CLAUDE_TOOL_MAP.get(str(t), []):
            if ct not in mapped:
                mapped.append(ct)
    return sorted(mapped)


def install_claude_code(
    repo_root: Path,
    scope: str,
    project: Path | None,
    target_dir: Path | None,
    method: str,
    dry_run: bool,
    uninstall: bool,
    force: bool,
) -> list[str]:
    if target_dir is not None:
        base = target_dir
    elif scope == "user":
        base = Path.home() / ".claude"
    else:
        if project is None:
            raise ValueError("--project is required for project scope.")
        base = project / ".claude"

    logs: list[str] = []
    skills = _iter_skills(repo_root)
    agents = _iter_enabled_agents(repo_root)
    rule_dst = base / "rules" / "aidlc.md"

    if uninstall:
        for s in skills:
            res = _remove_path(base / "skills" / s.name, dry_run)
            if res:
                logs.append(res)
        for agent_file, _, _ in agents:
            res = _remove_path(base / "agents" / agent_file.name, dry_run)
            if res:
                logs.append(res)
        res = _remove_path(rule_dst, dry_run)
        if res:
            logs.append(res)
        return logs or [f"nothing to uninstall in {base}"]

    for s in skills:
        logs.append(_install_dir_entry(s, base / "skills" / s.name, method, dry_run, force))

    for agent_file, fm, body in agents:
        claude_fm = {
            "name": fm.get("name", agent_file.stem),
            "description": fm.get("description", ""),
            "tools": _translate_claude_tools(fm.get("tools", [])),
        }
        content = f"{dump_frontmatter(claude_fm)}\n{body.lstrip()}"
        dst = base / "agents" / agent_file.name
        if dry_run:
            logs.append(f"[dry-run] write {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
            logs.append(f"wrote: {dst}")

    agents_rule = (repo_root / "rules" / "AGENTS.md").read_text(encoding="utf-8")
    _, gates_body = parse_frontmatter(
        (repo_root / "rules" / "gates.md").read_text(encoding="utf-8")
    )
    combined_rule = f"{agents_rule.rstrip()}\n\n---\n\n{gates_body.lstrip()}"
    if dry_run:
        logs.append(f"[dry-run] write {rule_dst}")
    else:
        rule_dst.parent.mkdir(parents=True, exist_ok=True)
        rule_dst.write_text(combined_rule, encoding="utf-8")
        logs.append(f"wrote: {rule_dst}")

    return logs


def install_cursor(
    repo_root: Path,
    scope: str,
    project: Path | None,
    target_dir: Path | None,
    method: str,
    dry_run: bool,
    uninstall: bool,
    force: bool,
) -> list[str]:
    if target_dir is not None:
        base = target_dir
    elif project is not None:
        base = project / ".cursor"
    else:
        raise ValueError("Cursor installation requires --project or --target-dir.")

    logs: list[str] = []
    skills = _iter_skills(repo_root)
    agents = _iter_enabled_agents(repo_root)
    core_mdc = base / "rules" / "core.mdc"
    gates_mdc = base / "rules" / "gates.mdc"

    if uninstall:
        for s in skills:
            res = _remove_path(base / "skills" / s.name, dry_run)
            if res:
                logs.append(res)
        for agent_file, _, _ in agents:
            res = _remove_path(base / "agents" / agent_file.name, dry_run)
            if res:
                logs.append(res)
        for p in (core_mdc, gates_mdc):
            res = _remove_path(p, dry_run)
            if res:
                logs.append(res)
        return logs or [f"nothing to uninstall in {base}"]

    for s in skills:
        logs.append(_install_dir_entry(s, base / "skills" / s.name, method, dry_run, force))

    core_body = (repo_root / "rules" / "AGENTS.md").read_text(encoding="utf-8")
    core_content = (
        f"{dump_frontmatter({'description': 'AI-DLC Agent Skills core guidelines', 'alwaysApply': True})}\n"
        f"{core_body.lstrip()}"
    )
    gates_fm, gates_body = parse_frontmatter(
        (repo_root / "rules" / "gates.md").read_text(encoding="utf-8")
    )
    gates_content = (
        f"{dump_frontmatter({'description': (gates_fm or {}).get('description', 'AI-DLC governance gates'), 'alwaysApply': False})}\n"
        f"{gates_body.lstrip()}"
    )
    for dst, text in ((core_mdc, core_content), (gates_mdc, gates_content)):
        if dry_run:
            logs.append(f"[dry-run] write {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8")
            logs.append(f"wrote: {dst}")

    for agent_file, fm, body in agents:
        cursor_fm = {
            "name": fm.get("name", agent_file.stem),
            "description": fm.get("description", ""),
        }
        dst = base / "agents" / agent_file.name
        content = f"{dump_frontmatter(cursor_fm)}\n{body.lstrip()}"
        if dry_run:
            logs.append(f"[dry-run] write {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
            logs.append(f"wrote: {dst}")

    return logs


def install_codex(
    repo_root: Path,
    scope: str,
    project: Path | None,
    target_dir: Path | None,
    method: str,
    dry_run: bool,
    uninstall: bool,
    force: bool,
) -> list[str]:
    if target_dir is not None:
        base = target_dir
    elif scope == "user":
        base = Path.home() / ".codex"
    else:
        if project is None:
            raise ValueError("--project is required for project scope.")
        base = project / ".codex"

    logs: list[str] = []
    skills = _iter_skills(repo_root)
    agents_md = base / "AGENTS.md"

    if uninstall:
        for s in skills:
            res = _remove_path(base / "skills" / s.name, dry_run)
            if res:
                logs.append(res)
        if agents_md.is_file():
            old = agents_md.read_text(encoding="utf-8")
            cleaned = remove_managed_block(old, CODEX_START_MARKER, CODEX_END_MARKER)
            if cleaned != old:
                if dry_run:
                    logs.append(f"[dry-run] strip managed block in {agents_md}")
                elif cleaned.strip():
                    agents_md.write_text(cleaned, encoding="utf-8")
                    logs.append(f"updated (removed AIDLC block): {agents_md}")
                else:
                    agents_md.unlink()
                    logs.append(f"removed empty: {agents_md}")
        return logs or [f"nothing to uninstall in {base}"]

    for s in skills:
        logs.append(_install_dir_entry(s, base / "skills" / s.name, method, dry_run, force))

    core_rules = (repo_root / "rules" / "AGENTS.md").read_text(encoding="utf-8").strip()
    _, gates_body = parse_frontmatter(
        (repo_root / "rules" / "gates.md").read_text(encoding="utf-8")
    )
    managed_inner = f"{core_rules}\n\n{gates_body.strip()}"
    existing = agents_md.read_text(encoding="utf-8") if agents_md.is_file() else ""
    updated = replace_managed_block(
        existing, CODEX_START_MARKER, CODEX_END_MARKER, managed_inner
    )
    if dry_run:
        logs.append(f"[dry-run] upsert managed block in {agents_md}")
    else:
        agents_md.parent.mkdir(parents=True, exist_ok=True)
        agents_md.write_text(updated, encoding="utf-8")
        logs.append(f"updated: {agents_md}")

    return logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or export AI-DLC Agent Skills across coding agent platforms."
    )
    parser.add_argument(
        "target",
        choices=["antigravity", "claude-code", "cursor", "codex", "all"],
    )
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--project", help="Target project directory (for project scope / cursor).")
    parser.add_argument(
        "--target-dir",
        help="Explicit destination root override (primarily for isolated installs/tests).",
    )
    parser.add_argument("--method", choices=["symlink", "copy"], default="copy")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--repo-root",
        default=str(SCRIPT_DIR.parent),
        help="Path to the agent-skills repository root.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    project = Path(args.project).resolve() if args.project else None
    target_dir = Path(args.target_dir).resolve() if args.target_dir else None

    targets = (
        ["antigravity", "claude-code", "cursor", "codex"]
        if args.target == "all"
        else [args.target]
    )
    if args.target == "all" and target_dir is not None:
        print("Error: --target-dir cannot be combined with 'all'.", file=sys.stderr)
        return 1

    dispatch = {
        "antigravity": install_antigravity,
        "claude-code": install_claude_code,
        "cursor": install_cursor,
        "codex": install_codex,
    }

    for t in targets:
        if t == "cursor" and project is None and target_dir is None:
            print(
                "Error: cursor target requires --project PATH (or --target-dir PATH).",
                file=sys.stderr,
            )
            return 1
        try:
            logs = dispatch[t](
                repo_root=repo_root,
                scope=args.scope,
                project=project,
                target_dir=target_dir,
                method=args.method,
                dry_run=args.dry_run,
                uninstall=args.uninstall,
                force=args.force,
            )
        except ValueError as exc:
            print(f"Error ({t}): {exc}", file=sys.stderr)
            return 1
        print(f"[{t}]")
        for line in logs:
            print(f"  {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
