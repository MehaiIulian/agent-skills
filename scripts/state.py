#!/usr/bin/env python3
"""Manage .aidlc/ project workflow state, gates, work units, and handoff ledger."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent

VALID_PHASES = ("triage", "inception", "construction", "operation", "completed")
VALID_MODES = ("strict", "balanced", "autonomous")
VALID_DEPTHS = ("auto", "fast-track", "standard", "deep")
VALID_UNIT_STATUSES = ("pending", "in_progress", "in_review", "approved", "blocked")
VALID_HANDOFF_STATUSES = (
    "READY",
    "BLOCKED",
    "NEEDS_REVIEW",
    "APPROVED",
    "CHANGES_REQUESTED",
)
VALID_APPROVERS = ("human", "verifier", "auto")

DEFAULT_GATE_MATRIX: dict[str, dict[str, str]] = {
    "strict": {
        "inception_to_construction": "human",
        "construction_to_operation": "human",
        "operation_to_completed": "human",
    },
    "balanced": {
        "inception_to_construction": "human",
        "construction_to_operation": "verifier",
        "operation_to_completed": "human",
    },
    "autonomous": {
        "inception_to_construction": "auto",
        "construction_to_operation": "verifier",
        "operation_to_completed": "auto",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_plugin_defaults() -> dict[str, Any]:
    cfg_path = PLUGIN_ROOT / "config" / "config.json"
    if cfg_path.is_file():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def aidlc_dir(project: Path) -> Path:
    return project / ".aidlc"


def state_path(project: Path) -> Path:
    return aidlc_dir(project) / "state.json"


def load_state(project: Path) -> dict[str, Any]:
    p = state_path(project)
    if not p.is_file():
        raise FileNotFoundError(
            f"No .aidlc/state.json found in {project}. Run 'state.py init' first."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(project: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    p = state_path(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def gate_policy(mode: str, transition_key: str) -> str:
    cfg = load_plugin_defaults()
    modes = cfg.get("governance", {}).get("modes", {})
    if mode in modes and transition_key in modes[mode].get("gates", {}):
        return modes[mode]["gates"][transition_key]
    return DEFAULT_GATE_MATRIX[mode][transition_key]


def allow_fast_track_skip_inception(mode: str) -> bool:
    cfg = load_plugin_defaults()
    modes = cfg.get("governance", {}).get("modes", {})
    if mode in modes and "allow_fast_track_skip_inception" in modes[mode]:
        return bool(modes[mode]["allow_fast_track_skip_inception"])
    return mode != "strict"


def cmd_init(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    base = aidlc_dir(project)
    if state_path(project).is_file() and not args.force:
        print(
            f"Error: {state_path(project)} already exists. Pass --force to reinitialize.",
            file=sys.stderr,
        )
        return 1

    cfg = load_plugin_defaults()
    gov = cfg.get("governance", {})
    mode = args.mode or gov.get("mode", "balanced")
    depth = args.depth or gov.get("default_depth", "auto")

    for sub in ("inception", "construction", "operation", "handoffs"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    initial_phase = "triage" if depth == "auto" else "inception"
    if depth == "fast-track" and allow_fast_track_skip_inception(mode):
        initial_phase = "construction"

    now = utc_now()
    state: dict[str, Any] = {
        "version": "1.0.0",
        "title": args.title,
        "intent": args.intent or "",
        "mode": mode,
        "depth": depth,
        "triage_rationale": "",
        "phase": initial_phase,
        "created_at": now,
        "updated_at": now,
        "gates": {
            "inception_to_construction": {"status": "pending", "approved_by": None, "at": None, "notes": ""},
            "construction_to_operation": {"status": "pending", "approved_by": None, "at": None, "notes": ""},
            "operation_to_completed": {"status": "pending", "approved_by": None, "at": None, "notes": ""},
        },
        "units": {},
        "handoffs": [],
    }
    save_state(project, state)
    print(
        f"Initialized AI-DLC workspace at {base} "
        f"(mode={mode}, depth={depth}, phase={initial_phase})."
    )
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    state = load_state(project)
    state["depth"] = args.depth
    state["triage_rationale"] = args.rationale

    if args.depth == "fast-track" and allow_fast_track_skip_inception(state["mode"]):
        state["phase"] = "construction"
        state["gates"]["inception_to_construction"] = {
            "status": "skipped_fast_track",
            "approved_by": "auto",
            "at": utc_now(),
            "notes": f"Fast-track triage: {args.rationale}",
        }
    else:
        state["phase"] = "inception"

    save_state(project, state)
    print(
        f"Triage complete: depth={state['depth']}, mode={state['mode']}, "
        f"phase={state['phase']}."
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    state = load_state(project)
    if args.json:
        print(json.dumps(state, indent=2))
        return 0

    print(f"Title  : {state['title']}")
    print(f"Phase  : {state['phase']} (mode={state['mode']}, depth={state['depth']})")
    if state.get("triage_rationale"):
        print(f"Triage : {state['triage_rationale']}")
    print("Gates  :")
    for g_name, g_info in state["gates"].items():
        print(
            f"  - {g_name}: {g_info['status']} "
            f"(by={g_info.get('approved_by') or '-'}, at={g_info.get('at') or '-'})"
        )
    print(f"Units  : {len(state['units'])}")
    for uid, unit in state["units"].items():
        print(
            f"  - [{uid}] {unit['title']} ({unit['status']}) "
            f"owner={unit['owner']} files={','.join(unit['files']) or '-'}"
        )
    print(f"Handoffs: {len(state['handoffs'])}")
    for h in state["handoffs"][-5:]:
        print(
            f"  - {h['id']} {h['from']} -> {h['to']} [{h['status']}] "
            f"{h['summary']}"
        )
    return 0


def _norm_file(path_str: str) -> str:
    return path_str.strip().lstrip("./")


def cmd_register_unit(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    state = load_state(project)
    files = [_norm_file(f) for f in args.files.split(",") if _norm_file(f)]
    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else []

    if not args.allow_overlap and files:
        new_set = set(files)
        for other_id, other in state["units"].items():
            if other_id == args.id or other["status"] == "approved":
                continue
            overlap = sorted(new_set & set(other.get("files", [])))
            if overlap:
                print(
                    f"Error: file ownership collision between unit '{args.id}' and "
                    f"active unit '{other_id}' on: {', '.join(overlap)}. "
                    f"Assign disjoint files or pass --allow-overlap explicitly.",
                    file=sys.stderr,
                )
                return 1

    state["units"][args.id] = {
        "id": args.id,
        "title": args.title,
        "owner": args.owner,
        "files": files,
        "skills": skills,
        "status": "pending",
        "notes": args.notes or "",
        "updated_at": utc_now(),
    }
    save_state(project, state)
    print(f"Registered unit '{args.id}' owned by '{args.owner}' ({len(files)} file(s)).")
    return 0


def cmd_update_unit(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    state = load_state(project)
    if args.id not in state["units"]:
        print(f"Error: unknown unit '{args.id}'.", file=sys.stderr)
        return 1
    unit = state["units"][args.id]
    unit["status"] = args.status
    if args.notes is not None:
        unit["notes"] = args.notes
    unit["updated_at"] = utc_now()
    save_state(project, state)
    print(f"Updated unit '{args.id}' -> status={args.status}.")
    return 0


def cmd_record_handoff(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    state = load_state(project)
    seq = len(state["handoffs"]) + 1
    handoff_id = f"H{seq:03d}"
    ts = utc_now()
    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else []
    artifacts = (
        [a.strip() for a in args.artifacts.split(",") if a.strip()]
        if args.artifacts
        else []
    )

    payload = {
        "id": handoff_id,
        "timestamp": ts,
        "from": args.from_agent,
        "to": args.to_agent,
        "phase": args.phase,
        "unit": args.unit or "",
        "status": args.status,
        "skills_used": skills,
        "artifacts": artifacts,
        "summary": args.summary,
    }
    handoffs_dir = aidlc_dir(project) / "handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{handoff_id}-{args.from_agent}-to-{args.to_agent}".replace("/", "-")
    (handoffs_dir / f"{slug}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    md = (
        f"## Handoff {handoff_id}: `{args.from_agent}` -> `{args.to_agent}`\n\n"
        f"- **Timestamp**: `{ts}`\n"
        f"- **Phase**: `{args.phase}`\n"
        f"- **Unit**: `{args.unit or 'N/A'}`\n"
        f"- **Status**: `{args.status}`\n"
        f"- **Skills Used**: {', '.join(skills) or 'N/A'}\n"
        f"- **Artifacts**: {', '.join(artifacts) or 'N/A'}\n\n"
        f"### Summary\n\n{args.summary}\n"
    )
    (handoffs_dir / f"{slug}.md").write_text(md, encoding="utf-8")

    state["handoffs"].append(payload)
    save_state(project, state)
    print(f"Recorded handoff {handoff_id}: {args.from_agent} -> {args.to_agent} [{args.status}].")
    return 0


def _required_approvers(policy: str) -> set[str]:
    if policy == "human":
        return {"human"}
    if policy == "verifier":
        return {"verifier", "human"}
    return {"auto", "verifier", "human"}


def cmd_advance(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    state = load_state(project)
    cur = state["phase"]
    target = args.to_phase
    mode = state["mode"]

    allowed_transitions = {
        "triage": {"inception", "construction"},
        "inception": {"construction"},
        "construction": {"operation"},
        "operation": {"completed"},
    }
    if cur not in allowed_transitions or target not in allowed_transitions[cur]:
        print(
            f"Error: invalid phase transition '{cur} -> {target}'. "
            f"Allowed from '{cur}': {sorted(allowed_transitions.get(cur, set())) or 'none'}.",
            file=sys.stderr,
        )
        return 1

    if cur == "triage" and target == "construction":
        if state["depth"] != "fast-track" or not allow_fast_track_skip_inception(mode):
            print(
                f"Error: cannot skip Inception from triage in mode='{mode}', depth='{state['depth']}'.",
                file=sys.stderr,
            )
            return 1
        state["phase"] = "construction"
        save_state(project, state)
        print("Advanced triage -> construction (fast-track).")
        return 0

    if cur == "triage" and target == "inception":
        state["phase"] = "inception"
        save_state(project, state)
        print("Advanced triage -> inception.")
        return 0

    gate_key = f"{cur}_to_{target}"
    policy = gate_policy(mode, gate_key)
    allowed_approvers = _required_approvers(policy)
    if args.approved_by not in allowed_approvers:
        print(
            f"Gate blocked ({gate_key}): mode '{mode}' requires approval by "
            f"{sorted(allowed_approvers)}, got '{args.approved_by}'.",
            file=sys.stderr,
        )
        return 1

    if cur == "construction":
        blocked_units = [
            uid for uid, u in state["units"].items() if u["status"] == "blocked"
        ]
        if blocked_units:
            print(
                f"Gate blocked (construction_to_operation): blocked units remain: {', '.join(blocked_units)}.",
                file=sys.stderr,
            )
            return 1
        incomplete_units = [
            uid for uid, u in state["units"].items() if u["status"] != "approved"
        ]
        if incomplete_units and args.approved_by != "human":
            print(
                "Gate blocked (construction_to_operation): units not yet approved: "
                f"{', '.join(incomplete_units)}.",
                file=sys.stderr,
            )
            return 1

    state["gates"][gate_key] = {
        "status": "approved",
        "approved_by": args.approved_by,
        "at": utc_now(),
        "notes": args.notes or "",
    }
    state["phase"] = target
    save_state(project, state)
    print(f"Gate '{gate_key}' approved by '{args.approved_by}'. Phase is now '{target}'.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage .aidlc/ workflow state, gates, units, and handoffs."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize .aidlc/ in a target project.")
    p_init.add_argument("--project", required=True)
    p_init.add_argument("--title", required=True)
    p_init.add_argument("--intent", default="")
    p_init.add_argument("--depth", choices=list(VALID_DEPTHS))
    p_init.add_argument("--mode", choices=list(VALID_MODES))
    p_init.add_argument("--force", action="store_true")

    p_triage = sub.add_parser("triage", help="Record adaptive depth triage.")
    p_triage.add_argument("--project", required=True)
    p_triage.add_argument("--depth", required=True, choices=["fast-track", "standard", "deep"])
    p_triage.add_argument("--rationale", required=True)

    p_status = sub.add_parser("status", help="Show workflow status.")
    p_status.add_argument("--project", required=True)
    p_status.add_argument("--json", action="store_true")

    p_reg = sub.add_parser("register-unit", help="Register a work unit and check file collisions.")
    p_reg.add_argument("--project", required=True)
    p_reg.add_argument("--id", required=True)
    p_reg.add_argument("--title", required=True)
    p_reg.add_argument("--owner", required=True)
    p_reg.add_argument("--files", default="")
    p_reg.add_argument("--skills", default="")
    p_reg.add_argument("--notes", default="")
    p_reg.add_argument("--allow-overlap", action="store_true")

    p_upd = sub.add_parser("update-unit", help="Update a work unit status.")
    p_upd.add_argument("--project", required=True)
    p_upd.add_argument("--id", required=True)
    p_upd.add_argument("--status", required=True, choices=list(VALID_UNIT_STATUSES))
    p_upd.add_argument("--notes")

    p_hand = sub.add_parser("record-handoff", help="Record an inter-agent handoff.")
    p_hand.add_argument("--project", required=True)
    p_hand.add_argument("--from", dest="from_agent", required=True)
    p_hand.add_argument("--to", dest="to_agent", required=True)
    p_hand.add_argument("--phase", required=True)
    p_hand.add_argument("--status", required=True, choices=list(VALID_HANDOFF_STATUSES))
    p_hand.add_argument("--summary", required=True)
    p_hand.add_argument("--unit", default="")
    p_hand.add_argument("--skills", default="")
    p_hand.add_argument("--artifacts", default="")

    p_adv = sub.add_parser("advance", help="Enforce gate policy and advance phase.")
    p_adv.add_argument("--project", required=True)
    p_adv.add_argument(
        "--to",
        dest="to_phase",
        required=True,
        choices=["inception", "construction", "operation", "completed"],
    )
    p_adv.add_argument("--approved-by", required=True, choices=list(VALID_APPROVERS))
    p_adv.add_argument("--notes", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "init": cmd_init,
        "triage": cmd_triage,
        "status": cmd_status,
        "register-unit": cmd_register_unit,
        "update-unit": cmd_update_unit,
        "record-handoff": cmd_record_handoff,
        "advance": cmd_advance,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
