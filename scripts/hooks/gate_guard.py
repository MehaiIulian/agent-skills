#!/usr/bin/env python3
"""Optional Antigravity lifecycle hook guarding phases, injecting state, and enforcing 50% context rotation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_context_policy() -> dict[str, int | bool]:
    defaults: dict[str, int | bool] = {
        "context_rotation_threshold_pct": 50,
        "max_steps_before_handoff": 25,
        "context_window_token_budget": 200000,
        "fresh_subagent_per_unit": True,
        "handoff_max_tokens": 1500,
    }
    cfg_file = PLUGIN_ROOT / "config" / "config.json"
    if not cfg_file.is_file():
        return defaults
    try:
        orch = json.loads(cfg_file.read_text(encoding="utf-8")).get("orchestration", {})
        for key in defaults:
            if key in orch:
                defaults[key] = orch[key]
    except (OSError, json.JSONDecodeError):
        pass
    return defaults


def _find_aidlc_state(payload: dict[str, Any]) -> tuple[Path, dict[str, Any]] | tuple[None, None]:
    candidates: list[Path] = []
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        candidates.append(Path(cwd))
    ws_paths = payload.get("workspacePaths")
    if isinstance(ws_paths, list):
        for p in ws_paths:
            if isinstance(p, str) and p:
                candidates.append(Path(p))

    for root in candidates:
        state_file = root / ".aidlc" / "state.json"
        if state_file.is_file():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                return root, data
            except (OSError, json.JSONDecodeError):
                continue
    return None, None


def _extract_target_path(payload: dict[str, Any]) -> str:
    sources: list[Any] = []
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        sources.append(tool_call.get("args"))
    sources.append(payload.get("toolInput"))
    sources.append(payload.get("args"))

    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in ("Path", "path", "TargetFile", "targetFile", "file_path"):
            val = src.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _is_inside_aidlc(target_path: str, project_root: Path | None) -> bool:
    if not target_path:
        return False
    p = Path(target_path)
    if project_root is not None:
        try:
            resolved_target = (p if p.is_absolute() else (project_root / p)).resolve()
            resolved_target.relative_to((project_root / ".aidlc").resolve())
            return True
        except ValueError:
            return False
    parts: list[str] = []
    for part in p.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            else:
                return False
        else:
            parts.append(part)
    return ".aidlc" in parts


def _inception_requires_approval(mode: str) -> bool:
    cfg_file = PLUGIN_ROOT / "config" / "config.json"
    if cfg_file.is_file():
        try:
            modes = json.loads(cfg_file.read_text(encoding="utf-8")).get("governance", {}).get("modes", {})
            gate = modes.get(mode, {}).get("gates", {}).get("inception_to_construction")
            if isinstance(gate, str):
                return gate != "auto"
        except (OSError, json.JSONDecodeError):
            pass
    return mode in ("strict", "balanced")


def _check_context_rotation(payload: dict[str, Any]) -> dict[str, Any]:
    policy = _load_context_policy()
    threshold_pct = int(policy["context_rotation_threshold_pct"])
    max_steps = int(policy["max_steps_before_handoff"])
    token_budget = int(policy["context_window_token_budget"])
    handoff_cap = int(policy["handoff_max_tokens"])

    reasons: list[str] = []
    steps = payload.get("initialNumSteps")
    if isinstance(steps, int) and steps >= max_steps:
        reasons.append(f"steps={steps} >= {max_steps}")

    transcript_path = payload.get("transcriptPath")
    if isinstance(transcript_path, str) and transcript_path:
        tp = Path(transcript_path)
        if tp.is_file():
            try:
                size_bytes = tp.stat().st_size
                est_tokens = size_bytes // 4
                est_pct = int((est_tokens / max(token_budget, 1)) * 100)
                if est_pct >= threshold_pct:
                    reasons.append(
                        f"estimated context ~{est_pct}% (~{est_tokens} tokens >= {threshold_pct}% of {token_budget})"
                    )
            except OSError:
                pass

    if not reasons:
        return {}

    msg = (
        f"[CONTEXT ROTATION GUARD >= {threshold_pct}%] Triggered ({'; '.join(reasons)}). "
        f"To prevent Context Rot, pause deep work now: record a compact Context-Pointer Handoff "
        f"(<= {handoff_cap} tokens: file paths, commits, .aidlc/state.json, remaining steps — NO raw logs) "
        f"via scripts/state.py record-handoff (or write .aidlc/handoffs/ / send a Handoff Envelope to orchestrator "
        f"if you do not have run_command) and spawn a fresh replacement subagent via invoke_subagent "
        f"(or recommend /compact if you are the primary chat agent)."
    )
    return {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}


def handle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("hookEventName", "")

    if event == "PreInvocation":
        return _check_context_rotation(payload)

    project_root, state = _find_aidlc_state(payload)
    if state is None:
        return {}

    phase = state.get("phase", "")
    mode = state.get("mode", "balanced")
    depth = state.get("depth", "standard")

    if event == "SessionStart":
        if phase == "completed":
            return {}
        units = state.get("units", {})
        active_units = [
            f"{uid}:{u.get('status', 'pending')}"
            for uid, u in units.items()
            if u.get("status") != "approved"
        ]
        summary = (
            f"[AI-DLC Active Session] Title: {state.get('title', 'Untitled')} | "
            f"Phase: {phase} | Mode: {mode} | Depth: {depth} | "
            f"Active units: {', '.join(active_units) if active_units else 'none'}. "
            f"Read .aidlc/state.json before making changes."
        )
        return {"injectSteps": [{"userMessage": summary}]}

    if event == "PreToolUse":
        if phase == "inception" and _inception_requires_approval(mode):
            target = _extract_target_path(payload)
            if target and not _is_inside_aidlc(target, project_root):
                return {
                    "decision": "ask",
                    "reason": (
                        f"AI-DLC {mode} mode: workflow is still in Inception. "
                        "Confirm before modifying files outside .aidlc/ prior to Inception gate approval."
                    ),
                }
        return {}

    return {}


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print("{}")
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            print("{}")
            return 0
        result = handle_payload(payload)
        print(json.dumps(result))
    except Exception:
        print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
