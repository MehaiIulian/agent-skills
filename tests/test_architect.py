#!/usr/bin/env python3
"""Comprehensive test suite for the AI-DLC `architect` agent.

Covers:
1. Frontmatter & config/schema/defaults parity (`agents/architect.md`, `config/*.json`)
2. Tool permissions & least-privilege design-only boundary
3. Bound skills, references, templates, and Markdown path integrity
4. Persona body responsibilities & collaborator wiring
5. Managed tuning block, context-rotation policy, and `scripts/tune.py` CLI lifecycle
6. Inception state lifecycle (`scripts/state.py`) and `gate_guard.py` hook behavior
7. Cross-platform installer export (`scripts/install.py`) & validator sensitivity (`scripts/validate.py`)
8. `workflows/pipeline.py` AST & schema integration
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import install  # noqa: E402
import tune  # noqa: E402
import validate  # noqa: E402
from _frontmatter import (  # noqa: E402
    RESERVED_AGENT_NAMES,
    TUNING_END_MARKER,
    TUNING_START_MARKER,
    VALID_ANTIGRAVITY_TOOLS_SET,
    VALID_EXEC_POLICIES_SET,
    VALID_MODELS_SET,
    parse_frontmatter,
)

AGENT_NAME = "architect"
AGENT_FILE = REPO_ROOT / "agents" / f"{AGENT_NAME}.md"
CONFIG_FILE = REPO_ROOT / "config" / "config.json"
DEFAULTS_FILE = REPO_ROOT / "config" / "defaults.json"
SCHEMA_FILE = REPO_ROOT / "config" / "config.schema.json"
PIPELINE_FILE = REPO_ROOT / "workflows" / "pipeline.py"

# Inception is design-only: the architect must never execute shell commands,
# manage background tasks, launch workflows, drive swarms, or schedule jobs.
FORBIDDEN_TOOLS = {"run_command", "manage_task", "run_workflow", "swarm", "schedule"}
REQUIRED_TOOLS = {
    "read_file",
    "write_file",
    "edit_file",
    "search_web",
    "ask_question",  # Business rules must be elicited, never guessed.
    "send_message",  # Consults `security`, hands off to `orchestrator`.
    "define_subagent",
    "invoke_subagent",
    "manage_subagents",
}
REQUIRED_SKILLS = (
    "requirements-discovery",
    "architecture-ddd",
    "task-decomposition",
    "subagent-orchestration",
)
COLLABORATORS = ("researcher", "security", "orchestrator")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_script(
    script_rel: str,
    *args: str,
    cwd: Path = REPO_ROOT,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(cwd / script_rel), *args],
        cwd=str(cwd),
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
    )


def copy_repo_to_temp(tmp_dir: str) -> Path:
    dst = Path(tmp_dir) / "repo"
    shutil.copytree(
        REPO_ROOT,
        dst,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".aidlc"),
    )
    return dst


def split_agent_doc(path: Path = AGENT_FILE) -> tuple[dict[str, Any], str]:
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm is not None, f"{path.name} must start with YAML frontmatter"
    return fm, body


def managed_block(body: str) -> str:
    start = body.index(TUNING_START_MARKER) + len(TUNING_START_MARKER)
    end = body.index(TUNING_END_MARKER)
    return body[start:end].strip()


def hand_written_body(body: str) -> str:
    """Body text outside the managed tuning block."""
    start = body.index(TUNING_START_MARKER)
    end = body.index(TUNING_END_MARKER) + len(TUNING_END_MARKER)
    return body[:start] + body[end:]


class ArchitectTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = load_json(CONFIG_FILE)
        cls.spec = cls.cfg["agents"][AGENT_NAME]
        cls.fm, cls.body = split_agent_doc()
        cls.raw = AGENT_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")


class TestArchitectFrontmatter(ArchitectTestBase):
    def test_agent_file_exists_and_name_is_valid(self) -> None:
        self.assertTrue(AGENT_FILE.is_file())
        self.assertEqual(self.fm["name"], AGENT_NAME)
        self.assertEqual(self.fm["name"], AGENT_FILE.stem)
        self.assertNotIn(self.fm["name"], RESERVED_AGENT_NAMES)

    def test_frontmatter_values_are_valid_enums(self) -> None:
        self.assertIn(self.fm["model"], VALID_MODELS_SET)
        self.assertIn(self.fm["commandExecutionPolicy"], VALID_EXEC_POLICIES_SET)
        for key in ("mainAgent", "subagent", "inheritMcp", "inheritCustomizations"):
            self.assertIsInstance(self.fm[key], bool, key)

    def test_config_spec_conforms_to_agent_schema(self) -> None:
        schema = load_json(SCHEMA_FILE)
        agent_schema = schema["$defs"]["agentSpec"]
        required_keys = set(agent_schema["required"])
        allowed_keys = set(agent_schema["properties"].keys())
        self.assertEqual(set(self.spec.keys()), required_keys)
        self.assertFalse(set(self.spec.keys()) - allowed_keys)
        self.assertIn(
            self.spec["phase"],
            agent_schema["properties"]["phase"]["enum"],
        )

    def test_frontmatter_mirrors_config(self) -> None:
        self.assertEqual(self.fm["description"], self.spec["description"])
        self.assertEqual(self.fm["model"], self.spec["model"])
        self.assertEqual(self.fm["commandExecutionPolicy"], self.spec["commandExecutionPolicy"])
        self.assertEqual(self.fm["mainAgent"], bool(self.spec["mainAgent"]) and self.spec["enabled"])
        self.assertEqual(self.fm["subagent"], bool(self.spec["subagent"]) and self.spec["enabled"])
        self.assertEqual(self.fm["inheritMcp"], bool(self.spec["inheritMcp"]))
        self.assertEqual(self.fm["inheritCustomizations"], bool(self.spec["inheritCustomizations"]))
        self.assertEqual(self.fm["tools"], self.spec["tools"])
        self.assertEqual(self.fm["skills"], [f"skills/{s}" for s in self.spec["skills"]])

    def test_description_covers_core_deliverables(self) -> None:
        desc = self.fm["description"]
        for term in ("Inception", "business rules", "Domain-Driven Design", "C4", "ADRs", "work units"):
            self.assertIn(term, desc)

    def test_architect_is_enabled_inception_agent_for_main_and_subagent(self) -> None:
        self.assertTrue(self.spec["enabled"])
        self.assertEqual(self.spec["phase"], "inception")
        self.assertEqual(self.fm["model"], "pro")
        self.assertTrue(self.fm["mainAgent"], "users can select architect directly")
        self.assertTrue(self.fm["subagent"], "orchestrator/pipeline invoke architect as a subagent")

    def test_defaults_contain_architect_with_same_contract(self) -> None:
        defaults = load_json(DEFAULTS_FILE)["agents"]
        self.assertIn(AGENT_NAME, defaults)
        d = defaults[AGENT_NAME]
        for key in ("phase", "description", "model", "tools", "skills", "can_spawn_subagents", "max_subagents"):
            self.assertEqual(d[key], self.spec[key], f"defaults.json drift on '{key}'")


class TestArchitectTools(ArchitectTestBase):
    def test_all_tools_are_valid_and_unique(self) -> None:
        tools = self.fm["tools"]
        self.assertEqual(len(tools), len(set(tools)), "duplicate tools")
        self.assertFalse(set(tools) - VALID_ANTIGRAVITY_TOOLS_SET)

    def test_required_tools_present(self) -> None:
        self.assertEqual(set(self.fm["tools"]), REQUIRED_TOOLS)

    def test_forbidden_tools_absent(self) -> None:
        self.assertFalse(
            FORBIDDEN_TOOLS & set(self.fm["tools"]),
            "architect is design-only; command/workflow/swarm/schedule tools are not allowed",
        )

    def test_dynamic_spawning_is_bounded(self) -> None:
        orch = self.cfg["orchestration"]
        self.assertTrue(self.spec["can_spawn_subagents"])
        self.assertGreater(self.spec["max_subagents"], 0)
        self.assertLessEqual(self.spec["max_subagents"], orch["max_parallel_subagents"])
        self.assertIn("manage_subagents", self.fm["tools"], "spawners must be able to clean up children")


class TestArchitectSkillsAndAssets(ArchitectTestBase):
    def test_required_skills_are_bound(self) -> None:
        self.assertEqual(tuple(self.spec["skills"]), REQUIRED_SKILLS)

    def test_bound_skills_exist_with_valid_inception_metadata(self) -> None:
        for skill in self.spec["skills"]:
            skill_md = REPO_ROOT / "skills" / skill / "SKILL.md"
            with self.subTest(skill=skill):
                self.assertTrue(skill_md.is_file(), skill_md)
                sfm, sbody = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
                self.assertIsNotNone(sfm)
                self.assertEqual(sfm["name"], skill)
                self.assertTrue(str(sfm.get("description", "")).strip())
                self.assertTrue(sbody.strip())
                meta = sfm.get("metadata") or {}
                if isinstance(meta, dict) and "phase" in meta:
                    self.assertIn(meta["phase"], ("inception", "all"))

    def test_every_repo_path_referenced_in_body_exists(self) -> None:
        refs = set(re.findall(r"`((?:skills|scripts|config|agents|rules|workflows)/[^`\s<>]+)`", self.body))
        self.assertTrue(refs, "expected the body to reference repo files")
        for ref in sorted(refs):
            with self.subTest(ref=ref):
                self.assertTrue((REPO_ROOT / ref).exists(), f"dangling reference: {ref}")

    def test_c4_and_adr_assets_have_complete_sections(self) -> None:
        base = REPO_ROOT / "skills" / "architecture-ddd"
        c4_file = base / "references" / "c4-diagrams.md"
        adr_file = base / "assets" / "adr-template.md"
        self.assertTrue(c4_file.is_file())
        self.assertTrue(adr_file.is_file())

        c4_text = c4_file.read_text(encoding="utf-8")
        for heading in ("Level 1", "Level 2", "Level 3", "Level 4"):
            self.assertIn(heading, c4_text)
        self.assertIn("```mermaid", c4_text)

        adr_text = adr_file.read_text(encoding="utf-8")
        for section in ("## Context", "## Decision", "## Alternatives Considered", "## Consequences & Reversibility"):
            self.assertIn(section, adr_text)

    def test_inception_artifact_templates_exist_and_align(self) -> None:
        assets_dir = REPO_ROOT / "skills" / "workflow" / "assets"
        req_tpl = (assets_dir / "requirements-template.md").read_text(encoding="utf-8")
        des_tpl = (assets_dir / "design-template.md").read_text(encoding="utf-8")
        uni_tpl = (assets_dir / "units-template.md").read_text(encoding="utf-8")

        for token in ("BR-1", "FR-1", "Given", "When", "Then", "Explicit Non-Goals"):
            self.assertIn(token, req_tpl)
        for token in ("Bounded Context", "BR-1", "C4 Architecture Diagrams", "ADR-001"):
            self.assertIn(token, des_tpl)
        for token in ("Unit ID", "Wave", "Owned Files (Disjoint per Wave)", "Dependencies", "Required Skills", "BR-1"):
            self.assertIn(token, uni_tpl)

    def test_orchestration_references_support_architect_handoffs(self) -> None:
        refs_dir = REPO_ROOT / "skills" / "subagent-orchestration" / "references"
        handoff_doc = (refs_dir / "handoff-protocol.md").read_text(encoding="utf-8")
        dyn_doc = (refs_dir / "dynamic-subagent-templates.md").read_text(encoding="utf-8")
        self.assertIn("architect", handoff_doc)
        for status in ("READY", "NEEDS_REVIEW", "CHANGES_REQUESTED", "APPROVED", "BLOCKED"):
            self.assertIn(status, handoff_doc)
        self.assertIn("Inception", dyn_doc)


class TestArchitectBody(ArchitectTestBase):
    def test_business_rules_come_first(self) -> None:
        resp = self.body.index("## Core Responsibilities")
        first_item = self.body.index("1. ", resp)
        self.assertIn("Business Rules", self.body[first_item : first_item + 200])
        self.assertIn("Never guess business logic", self.body)

    def test_requirement_id_conventions_documented(self) -> None:
        for prefix in ("BR-", "FR-", "NFR-"):
            self.assertIn(f"`{prefix}", self.body, prefix)
        self.assertIn("Given/When/Then", self.body)

    def test_inception_artifacts_and_design_only_guardrail_documented(self) -> None:
        self.assertIn(".aidlc/inception/requirements.md", self.body)
        self.assertIn(".aidlc/inception/design.md", self.body)
        self.assertIn(".aidlc/inception/units.md", self.body)
        self.assertIn("ONLY inside `.aidlc/inception/`", self.body)
        self.assertIn("never attempt shell commands", self.body)

    def test_c4_levels_are_depth_calibrated(self) -> None:
        for level in ("L1 System Context", "L2 Container", "L3 Component", "L4"):
            self.assertIn(level, self.body)
        self.assertIn("`standard`", self.body)
        self.assertIn("`deep`", self.body)

    def test_unit_decomposition_requires_disjoint_ownership_and_orchestrator_handoff(self) -> None:
        self.assertIn("disjoint file ownership", self.body)
        self.assertIn("depends_on", self.body)
        self.assertIn("register-unit", self.body)
        self.assertIn("`orchestrator` registers each unit", self.body)

    def test_state_register_unit_subcommand_exists(self) -> None:
        proc = run_script("scripts/state.py", "register-unit", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for flag in ("--files", "--skills", "--depends-on", "--wave", "--allow-overlap"):
            self.assertIn(flag, proc.stdout)

    def test_collaborators_exist_and_security_supports_inception_delegation(self) -> None:
        for peer in COLLABORATORS:
            with self.subTest(peer=peer):
                self.assertIn(f"`{peer}`", self.body)
                self.assertIn(peer, self.cfg["agents"])
                self.assertTrue(self.cfg["agents"][peer]["enabled"])
                self.assertTrue((REPO_ROOT / "agents" / f"{peer}.md").is_file())
        self.assertIn(self.cfg["agents"]["security"]["phase"], ("all", "inception"))
        self.assertIn('TypeName: "security"', self.body)


class TestArchitectTuningAndCLI(ArchitectTestBase):
    def test_exactly_one_managed_block(self) -> None:
        self.assertEqual(self.raw.count(TUNING_START_MARKER), 1)
        self.assertEqual(self.raw.count(TUNING_END_MARKER), 1)
        self.assertLess(self.raw.index(TUNING_START_MARKER), self.raw.index(TUNING_END_MARKER))

    def test_managed_block_in_sync_with_config(self) -> None:
        expected = tune.render_tuning_block(AGENT_NAME, self.spec, self.cfg).strip()
        self.assertEqual(managed_block(self.body), expected)

    def test_context_rotation_policy_synced_into_tuning_block(self) -> None:
        orch = self.cfg["orchestration"]
        block = managed_block(self.body)
        self.assertIn("Context Rotation Policy", block)
        self.assertIn(f"`{orch['context_rotation_threshold_pct']}%`", block)
        self.assertIn(f"`>= {orch['max_steps_before_handoff']}`", block)
        self.assertIn(f"`<= {orch['handoff_max_tokens']}`", block)

    def test_document_is_idempotent_under_apply(self) -> None:
        rendered = tune.render_agent_document(AGENT_NAME, self.spec, self.cfg, existing_text=self.raw)
        self.assertEqual(rendered, self.raw, "run `python3 scripts/tune.py apply`")
        again = tune.render_agent_document(AGENT_NAME, self.spec, self.cfg, existing_text=rendered)
        self.assertEqual(again, rendered)

    def test_spawn_line_reflects_limits(self) -> None:
        block = managed_block(self.body)
        orch = self.cfg["orchestration"]
        self.assertIn(f"max {self.spec['max_subagents']} child subagents", block)
        self.assertIn(f"global nesting cap {orch['max_nesting_depth']}", block)

    def test_retune_preserves_hand_written_instructions(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        spec = cfg["agents"][AGENT_NAME]
        spec["model"] = "flash"
        spec["custom_instructions"] = ["Always produce an L3 diagram for new services."]
        rendered = tune.render_agent_document(AGENT_NAME, spec, cfg, existing_text=self.raw)
        fm, body = parse_frontmatter(rendered)
        assert fm is not None
        self.assertEqual(fm["model"], "flash")
        self.assertIn("1. Always produce an L3 diagram for new services.", managed_block(body))
        self.assertEqual(hand_written_body(body).strip(), hand_written_body(self.body).strip())

    def test_disabling_spawning_updates_block(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"][AGENT_NAME]["can_spawn_subagents"] = False
        block = tune.render_tuning_block(AGENT_NAME, cfg["agents"][AGENT_NAME], cfg)
        self.assertIn("Dynamic Subagent Spawning**: Disabled", block)

    def test_disabled_agent_is_hidden(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"][AGENT_NAME]["enabled"] = False
        rendered = tune.render_agent_document(AGENT_NAME, cfg["agents"][AGENT_NAME], cfg, existing_text=self.raw)
        fm, body = parse_frontmatter(rendered)
        assert fm is not None
        self.assertFalse(fm["mainAgent"])
        self.assertFalse(fm["subagent"])
        self.assertIn("DISABLED", managed_block(body))

    def test_tune_cli_roundtrip_on_isolated_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo_to_temp(tmp)
            original_architect = (repo / "agents" / "architect.md").read_text(encoding="utf-8")

            p_tune = run_script(
                "scripts/tune.py",
                "tune-agent",
                AGENT_NAME,
                "--model",
                "flash",
                "--max-subagents",
                "3",
                "--add-skill",
                "security-audit",
                "--instruction",
                "Require ADR for every new external dependency.",
                cwd=repo,
            )
            self.assertEqual(p_tune.returncode, 0, p_tune.stderr)

            fm, body = split_agent_doc(repo / "agents" / "architect.md")
            self.assertEqual(fm["model"], "flash")
            self.assertIn("skills/security-audit", fm["skills"])
            self.assertIn("max 3 child subagents", managed_block(body))
            self.assertIn("Require ADR for every new external dependency.", managed_block(body))

            report = validate.run_validation(repo)
            self.assertEqual(report.error_count, 0, report.findings)

            # Invalid tool on architect is rejected cleanly
            p_bad = run_script(
                "scripts/tune.py",
                "tune-agent",
                AGENT_NAME,
                "--add-tool",
                "not_a_real_tool",
                cwd=repo,
            )
            self.assertNotEqual(p_bad.returncode, 0)

            # Reset restores exact baseline
            p_reset = run_script("scripts/tune.py", "reset", cwd=repo)
            self.assertEqual(p_reset.returncode, 0, p_reset.stderr)
            self.assertEqual(
                (repo / "agents" / "architect.md").read_text(encoding="utf-8"),
                original_architect,
            )


class TestArchitectInceptionLifecycleAndHooks(unittest.TestCase):
    def test_inception_artifacts_units_handoff_and_gate_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "sample-app"
            proj.mkdir()

            p_init = run_script(
                "scripts/state.py",
                "init",
                "--project",
                str(proj),
                "--title",
                "Order Cancellation",
                "--intent",
                "Allow customers to cancel pending orders within 30 minutes",
                "--mode",
                "balanced",
            )
            self.assertEqual(p_init.returncode, 0, p_init.stderr)

            p_triage = run_script(
                "scripts/state.py",
                "triage",
                "--project",
                str(proj),
                "--depth",
                "standard",
                "--rationale",
                "Multi-module domain policy with new BR-1 cancellation invariant",
            )
            self.assertEqual(p_triage.returncode, 0, p_triage.stderr)

            # Architect writes Inception deliverables inside .aidlc/inception/
            inc_dir = proj / ".aidlc" / "inception"
            (inc_dir / "requirements.md").write_text("# Requirements\n- BR-1\n- FR-1\n", encoding="utf-8")
            (inc_dir / "design.md").write_text("# Design\n- OrderAggregate enforces BR-1\n", encoding="utf-8")

            # Register disjoint units U1 & U2
            p_u1 = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U1",
                "--title",
                "Order cancellation domain invariant (BR-1)",
                "--owner",
                "developer",
                "--files",
                "src/orders/domain.py,tests/test_orders_domain.py",
                "--skills",
                "tdd-implementation",
            )
            self.assertEqual(p_u1.returncode, 0, p_u1.stderr)

            p_u2 = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U2",
                "--title",
                "Cancel order HTTP endpoint (FR-1)",
                "--owner",
                "developer",
                "--files",
                "src/orders/api.py,tests/test_orders_api.py",
                "--skills",
                "tdd-implementation",
            )
            self.assertEqual(p_u2.returncode, 0, p_u2.stderr)

            # Overlapping file ownership in the same wave is rejected
            p_collide = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U3",
                "--title",
                "Conflicting edit on domain.py",
                "--owner",
                "developer",
                "--files",
                "./src/orders/domain.py,tests/test_extra.py",
            )
            self.assertNotEqual(p_collide.returncode, 0)
            self.assertIn("collision", p_collide.stderr.lower())

            # Serialized downstream unit (--depends-on U1) may touch U1's file without --allow-overlap
            p_u3_wave2 = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U3",
                "--title",
                "Follow-up audit hook on domain.py",
                "--owner",
                "developer",
                "--files",
                "src/orders/domain.py,.github/workflows/ci.yml",
                "--depends-on",
                "U1",
                "--wave",
                "2",
            )
            self.assertEqual(p_u3_wave2.returncode, 0, p_u3_wave2.stderr)

            # Another Wave 2 unit touching the same file as U3 still collides
            p_u4_collide = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U4",
                "--title",
                "Concurrent Wave 2 conflict",
                "--owner",
                "developer",
                "--files",
                "src/orders/domain.py",
                "--depends-on",
                "U1",
                "--wave",
                "2",
            )
            self.assertNotEqual(p_u4_collide.returncode, 0)
            self.assertIn("collision", p_u4_collide.stderr.lower())

            # Dotfile paths stay distinct from non-dotfile paths (no over-stripping of leading '.')
            p_u4_dotfile_ok = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U4",
                "--title",
                "Docs mentioning github workflow path",
                "--owner",
                "developer",
                "--files",
                "github/workflows/ci.yml",
                "--depends-on",
                "U1",
                "--wave",
                "2",
            )
            self.assertEqual(p_u4_dotfile_ok.returncode, 0, p_u4_dotfile_ok.stderr)

            # Record Inception handoff from architect -> orchestrator
            p_ho = run_script(
                "scripts/state.py",
                "record-handoff",
                "--project",
                str(proj),
                "--from",
                AGENT_NAME,
                "--to",
                "orchestrator",
                "--phase",
                "inception",
                "--status",
                "READY",
                "--skills",
                "requirements-discovery,architecture-ddd,task-decomposition",
                "--artifacts",
                ".aidlc/inception/requirements.md,.aidlc/inception/design.md",
                "--summary",
                "Completed BR-1/FR-1 specs, L3 C4 design, and 2 disjoint units.",
            )
            self.assertEqual(p_ho.returncode, 0, p_ho.stderr)
            self.assertTrue((proj / ".aidlc" / "handoffs" / "H001-architect-to-orchestrator.md").is_file())

            # In balanced mode, inception -> construction blocks 'auto' and 'verifier', requires 'human'
            for non_human in ("auto", "verifier"):
                p_block = run_script(
                    "scripts/state.py",
                    "advance",
                    "--project",
                    str(proj),
                    "--to",
                    "construction",
                    "--approved-by",
                    non_human,
                )
                self.assertNotEqual(p_block.returncode, 0)

            p_ok = run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(proj),
                "--to",
                "construction",
                "--approved-by",
                "human",
            )
            self.assertEqual(p_ok.returncode, 0, p_ok.stderr)
            state = load_json(proj / ".aidlc" / "state.json")
            self.assertEqual(state["phase"], "construction")
            self.assertEqual(state["gates"]["inception_to_construction"]["approved_by"], "human")

    def test_gate_guard_allows_aidlc_artifacts_and_guards_gated_src_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ("strict", "balanced"):
                proj = Path(tmp) / f"{mode}-app"
                proj.mkdir()
                run_script(
                    "scripts/state.py",
                    "init",
                    "--project",
                    str(proj),
                    "--title",
                    f"{mode} Run",
                    "--mode",
                    mode,
                    "--depth",
                    "deep",
                )

                for artifact in ("requirements.md", "design.md", "units.md", "adr-001.md"):
                    p_allow = run_script(
                        "scripts/hooks/gate_guard.py",
                        stdin_text=json.dumps(
                            {
                                "hookEventName": "PreToolUse",
                                "cwd": str(proj),
                                "toolCall": {
                                    "id": "w1",
                                    "name": "write_file",
                                    "args": {"Path": str(proj / ".aidlc" / "inception" / artifact)},
                                },
                            }
                        ),
                    )
                    self.assertEqual(p_allow.returncode, 0)
                    self.assertEqual(json.loads(p_allow.stdout), {})

                p_src = run_script(
                    "scripts/hooks/gate_guard.py",
                    stdin_text=json.dumps(
                        {
                            "hookEventName": "PreToolUse",
                            "cwd": str(proj),
                            "toolCall": {
                                "id": "w2",
                                "name": "write_file",
                                "args": {"Path": str(proj / "src" / "domain.py")},
                            },
                        }
                    ),
                )
                self.assertEqual(p_src.returncode, 0)
                self.assertEqual(json.loads(p_src.stdout).get("decision"), "ask", mode)

                # Path traversal escaping .aidlc/ via '..' must NOT bypass the guard
                p_escape = run_script(
                    "scripts/hooks/gate_guard.py",
                    stdin_text=json.dumps(
                        {
                            "hookEventName": "PreToolUse",
                            "cwd": str(proj),
                            "toolCall": {
                                "id": "w2b",
                                "name": "write_file",
                                "args": {"Path": str(proj / ".aidlc" / ".." / "src" / "domain.py")},
                            },
                        }
                    ),
                )
                self.assertEqual(p_escape.returncode, 0)
                self.assertEqual(json.loads(p_escape.stdout).get("decision"), "ask", mode)

            # In autonomous mode (inception_to_construction == 'auto'), PreToolUse does not prompt
            auto_proj = Path(tmp) / "autonomous-app"
            auto_proj.mkdir()
            run_script(
                "scripts/state.py",
                "init",
                "--project",
                str(auto_proj),
                "--title",
                "Auto Run",
                "--mode",
                "autonomous",
                "--depth",
                "standard",
            )
            p_auto_src = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreToolUse",
                        "cwd": str(auto_proj),
                        "toolCall": {
                            "id": "w3",
                            "name": "write_file",
                            "args": {"Path": str(auto_proj / "src" / "domain.py")},
                        },
                    }
                ),
            )
            self.assertEqual(p_auto_src.returncode, 0)
            self.assertEqual(json.loads(p_auto_src.stdout), {})

    def test_gate_guard_preinvocation_context_rotation_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            small_tx = Path(tmp) / "small.jsonl"
            small_tx.write_text("x" * 1024, encoding="utf-8")

            p_quiet = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreInvocation",
                        "initialNumSteps": 5,
                        "transcriptPath": str(small_tx),
                    }
                ),
            )
            self.assertEqual(p_quiet.returncode, 0)
            self.assertEqual(json.loads(p_quiet.stdout), {})

            # Step threshold (>= 25) triggers rotation message with non-CLI fallback for architect
            p_steps = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreInvocation",
                        "initialNumSteps": 25,
                        "transcriptPath": str(small_tx),
                    }
                ),
            )
            self.assertEqual(p_steps.returncode, 0)
            out_steps = json.loads(p_steps.stdout)
            sys_msg = out_steps["injectSteps"][0]["systemMessage"]["systemMessage"]
            self.assertIn("CONTEXT ROTATION GUARD", sys_msg)
            self.assertIn("do not have run_command", sys_msg)

            # Token budget threshold (>= 50% of 200k tokens ~= 400k bytes) triggers rotation message
            large_tx = Path(tmp) / "large.jsonl"
            large_tx.write_text("a" * 420_000, encoding="utf-8")
            p_bytes = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreInvocation",
                        "initialNumSteps": 3,
                        "transcriptPath": str(large_tx),
                    }
                ),
            )
            self.assertEqual(p_bytes.returncode, 0)
            out_bytes = json.loads(p_bytes.stdout)
            self.assertIn(
                "estimated context ~",
                out_bytes["injectSteps"][0]["systemMessage"]["systemMessage"],
            )


class TestArchitectCrossPlatformInstallAndValidation(unittest.TestCase):
    def test_claude_code_export_translates_architect_tools_without_bash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "claude"
            install.install_claude_code(
                repo_root=REPO_ROOT,
                scope="user",
                project=None,
                target_dir=dst,
                method="copy",
                dry_run=False,
                uninstall=False,
                force=True,
            )
            exported = dst / "agents" / "architect.md"
            self.assertTrue(exported.is_file())
            fm, body = split_agent_doc(exported)
            self.assertEqual(fm["name"], AGENT_NAME)
            self.assertEqual(
                fm["tools"],
                ["Agent", "AskUserQuestion", "Edit", "Glob", "Grep", "Read", "WebSearch", "Write"],
            )
            self.assertNotIn("Bash", fm["tools"])
            self.assertIn("## Core Responsibilities", body)
            for skill in REQUIRED_SKILLS:
                self.assertTrue((dst / "skills" / skill / "SKILL.md").is_file())

    def test_cursor_and_antigravity_exports_include_architect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ag_dst = Path(tmp) / "ag"
            install.install_antigravity(
                repo_root=REPO_ROOT,
                scope="user",
                project=None,
                target_dir=ag_dst,
                method="copy",
                dry_run=False,
                uninstall=False,
                force=True,
            )
            ag_arch = ag_dst / "agent-skills" / "agents" / "architect.md"
            self.assertTrue(ag_arch.is_file())
            self.assertFalse((ag_dst / "agent-skills" / "tests").exists())

            cur_dst = Path(tmp) / "cursor"
            install.install_cursor(
                repo_root=REPO_ROOT,
                scope="project",
                project=None,
                target_dir=cur_dst,
                method="copy",
                dry_run=False,
                uninstall=False,
                force=True,
            )
            cur_arch = cur_dst / "agents" / "architect.md"
            self.assertTrue(cur_arch.is_file())
            cur_fm, _ = split_agent_doc(cur_arch)
            self.assertEqual(set(cur_fm.keys()), {"name", "description"})

    def test_codex_export_includes_architect_skills_and_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_dst = Path(tmp) / "codex"
            install.install_codex(
                repo_root=REPO_ROOT,
                scope="user",
                project=None,
                target_dir=codex_dst,
                method="copy",
                dry_run=False,
                uninstall=False,
                force=True,
            )
            for skill in REQUIRED_SKILLS:
                self.assertTrue((codex_dst / "skills" / skill / "SKILL.md").is_file(), skill)
            agents_md = (codex_dst / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("architect", agents_md)

    def test_disabled_architect_is_skipped_by_enabled_agent_exporters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo_to_temp(tmp)
            p_dis = run_script("scripts/tune.py", "tune-agent", AGENT_NAME, "--disable", cwd=repo)
            self.assertEqual(p_dis.returncode, 0, p_dis.stderr)
            dst = Path(tmp) / "claude-disabled"
            install.install_claude_code(
                repo_root=repo,
                scope="user",
                project=None,
                target_dir=dst,
                method="copy",
                dry_run=False,
                uninstall=False,
                force=True,
            )
            self.assertFalse((dst / "agents" / "architect.md").exists())

    def test_validator_catches_architect_drift_and_invalid_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = copy_repo_to_temp(tmp)
            arch_path = repo / "agents" / "architect.md"
            original = arch_path.read_text(encoding="utf-8")

            # 1. Manual edit to frontmatter causes config drift error
            arch_path.write_text(original.replace("model: pro", "model: flash", 1), encoding="utf-8")
            rep_drift = validate.run_validation(repo)
            self.assertGreater(rep_drift.error_count, 0)
            self.assertTrue(any("drift" in f["message"].lower() for f in rep_drift.findings))

            # 2. Removing tuning markers is flagged
            stripped = re.sub(
                r"<!-- AIDLC:TUNING:START -->.*?<!-- AIDLC:TUNING:END -->",
                "",
                original,
                flags=re.DOTALL,
            )
            arch_path.write_text(stripped, encoding="utf-8")
            rep_markers = validate.run_validation(repo)
            self.assertGreater(rep_markers.error_count, 0)
            self.assertTrue(any("tuning markers" in f["message"].lower() for f in rep_markers.findings))


class TestArchitectPipelineWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PIPELINE_FILE.read_text(encoding="utf-8")
        cls.tree = compile(
            cls.source,
            str(PIPELINE_FILE),
            "exec",
            flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )
        # Evaluate only the top-level *_SCHEMA dict literals.
        cls.schemas: dict[str, Any] = {}
        for node in cls.tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.endswith("_SCHEMA")
            ):
                expr = ast.Expression(node.value)
                cls.schemas[node.targets[0].id] = eval(  # noqa: S307 - literals only
                    compile(expr, str(PIPELINE_FILE), "eval"),
                    {"__builtins__": {}},
                    dict(cls.schemas),
                )
        cls.agent_calls = [
            n
            for n in ast.walk(cls.tree)
            if isinstance(n, ast.Call)
            and any(k.arg == "type_name" and isinstance(k.value, ast.Constant) for k in n.keywords)
        ]
        cls.architect_calls = [
            n
            for n in cls.agent_calls
            if any(
                k.arg == "type_name" and isinstance(k.value, ast.Constant) and k.value.value == AGENT_NAME
                for k in n.keywords
            )
        ]

    def _kw(self, call: ast.Call, name: str) -> ast.expr:
        return next(k.value for k in call.keywords if k.arg == name)

    def test_pipeline_invokes_architect_exactly_once_with_inherit_workspace(self) -> None:
        self.assertEqual(len(self.architect_calls), 1)
        ws = self._kw(self.architect_calls[0], "workspace")
        self.assertIsInstance(ws, ast.Constant)
        self.assertEqual(ws.value, "inherit")

    def test_architect_runs_after_researcher_and_consumes_research_brief(self) -> None:
        researcher_calls = [
            n
            for n in self.agent_calls
            if any(
                k.arg == "type_name" and isinstance(k.value, ast.Constant) and k.value.value == "researcher"
                for k in n.keywords
            )
        ]
        self.assertEqual(len(researcher_calls), 1)
        self.assertLess(researcher_calls[0].lineno, self.architect_calls[0].lineno)
        prompt_src = ast.unparse(self._kw(self.architect_calls[0], "prompt"))
        self.assertIn("research_brief", prompt_src)

    def test_architect_call_uses_architecture_schema(self) -> None:
        schema = self._kw(self.architect_calls[0], "schema")
        self.assertIsInstance(schema, ast.Name)
        self.assertEqual(schema.id, "ARCHITECTURE_SCHEMA")

    def test_architecture_schema_contract(self) -> None:
        arch = self.schemas["ARCHITECTURE_SCHEMA"]
        self.assertEqual(set(arch["required"]), {"summary", "business_rules", "design_doc", "units"})
        self.assertEqual(arch["properties"]["business_rules"]["type"], "array")
        units = arch["properties"]["units"]
        self.assertEqual(units["type"], "array")
        self.assertGreaterEqual(units["minItems"], 1)
        item = units["items"]
        self.assertTrue(
            {"id", "title", "files", "depends_on", "acceptance_criteria", "skills"} <= set(item["required"])
        )
        self.assertEqual(item["properties"]["files"]["type"], "array")
        self.assertEqual(item["properties"]["depends_on"]["type"], "array")

    def test_prompt_references_all_inception_skills_and_artifacts(self) -> None:
        prompt_src = ast.unparse(self._kw(self.architect_calls[0], "prompt"))
        mentioned = set(re.findall(r"skills/([a-z0-9-]+)/SKILL\.md", prompt_src))
        self.assertEqual(
            mentioned,
            {"requirements-discovery", "architecture-ddd", "task-decomposition"},
        )
        bound = set(load_json(CONFIG_FILE)["agents"][AGENT_NAME]["skills"])
        self.assertFalse(mentioned - bound, f"prompt uses unbound skills: {mentioned - bound}")
        for token in ("disjoint", "depends_on", "requirements.md", "design.md", "units.md"):
            self.assertIn(token, prompt_src)

    def test_pipeline_wave_scheduler_and_file_overlap_helpers(self) -> None:
        helper_names = {"_norm_unit_path", "_wave_has_file_overlap", "_compute_unit_waves"}
        helper_nodes = [
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ]
        self.assertEqual({n.name for n in helper_nodes}, helper_names)
        mod = ast.Module(body=helper_nodes, type_ignores=[])
        ns: dict[str, Any] = {}
        exec(compile(mod, str(PIPELINE_FILE), "exec"), ns)  # noqa: S102 - pure helper functions

        units = [
            {"id": "U0", "files": ["src/contracts.py"], "depends_on": []},
            {"id": "U1", "files": ["src/service_a.py"], "depends_on": ["U0"]},
            {"id": "U2", "files": ["src/service_b.py"], "depends_on": ["U0"]},
            {"id": "U3", "files": ["src/api.py"], "depends_on": ["U1", "U2"]},
        ]
        waves = ns["_compute_unit_waves"](units)
        self.assertEqual([[u["id"] for u in w] for w in waves], [["U0"], ["U1", "U2"], ["U3"]])
        self.assertFalse(ns["_wave_has_file_overlap"](waves[1]))

        # Normalized "./src/x.py" vs "src/x.py" overlap is detected
        self.assertTrue(
            ns["_wave_has_file_overlap"](
                [
                    {"id": "A", "files": ["./src/shared.py"]},
                    {"id": "B", "files": ["src/shared.py"]},
                ]
            )
        )

        # Dotfile paths keep their leading dot; "./.env" normalizes to ".env"
        self.assertEqual(ns["_norm_unit_path"](".github/workflows/ci.yml"), ".github/workflows/ci.yml")
        self.assertEqual(ns["_norm_unit_path"]("./.env"), ".env")
        self.assertFalse(
            ns["_wave_has_file_overlap"](
                [
                    {"id": "A", "files": [".github/workflows/ci.yml"]},
                    {"id": "B", "files": ["github/workflows/ci.yml"]},
                ]
            )
        )

        # Unknown/external depends_on IDs do not stall wave scheduling
        ext_waves = ns["_compute_unit_waves"](
            [{"id": "U1", "files": ["a.py"], "depends_on": ["EXTERNAL_PRECONDITION"]}]
        )
        self.assertEqual([[u["id"] for u in w] for w in ext_waves], [["U1"]])

        # Dependency cycles degrade gracefully without infinite loops
        cyclic = [
            {"id": "C1", "files": ["a.py"], "depends_on": ["C2"]},
            {"id": "C2", "files": ["b.py"], "depends_on": ["C1"]},
        ]
        cyclic_waves = ns["_compute_unit_waves"](cyclic)
        self.assertEqual([[u["id"] for u in w] for w in cyclic_waves], [["C1"], ["C2"]])

        # Parallel share-workspace waves integrate branches back before subsequent waves/verification
        self.assertIn("Integrate Wave", self.source)

    def test_architect_runs_in_inception_and_feeds_construction_agents(self) -> None:
        call_line = self.architect_calls[0].lineno
        phases = [
            (n.lineno, n.args[0].value)
            for n in ast.walk(self.tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "phase"
            and n.args
            and isinstance(n.args[0], ast.Constant)
        ]
        current = max((p for p in phases if p[0] < call_line), default=(0, ""))[1]
        self.assertTrue(current.startswith("Inception"), current)

        # Downstream developer/verifier/security prompts consume business_rules, design_doc, and units
        normalized_src = self.source.replace('"', "'")
        self.assertIn("business_rules_block", normalized_src)
        self.assertIn("plan['design_doc']", normalized_src)
        self.assertIn("plan['units']", normalized_src)


if __name__ == "__main__":
    unittest.main()
