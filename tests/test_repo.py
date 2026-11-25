#!/usr/bin/env python3
"""Automated test suite for AI-DLC Agent Skills repository."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _frontmatter import CODEX_END_MARKER, CODEX_START_MARKER, parse_frontmatter


def run_script(script_rel: str, *args: str, stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script_rel), *args],
        cwd=str(REPO_ROOT),
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
    )


class TestAidlcAgentSkillsRepo(unittest.TestCase):
    def test_repo_validates_cleanly(self) -> None:
        proc = run_script("scripts/validate.py", "--json")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["errors"], 0, msg=report)
        self.assertEqual(report["warnings"], 0, msg=report)

    def test_tune_check_in_sync(self) -> None:
        proc = run_script("scripts/tune.py", "apply", "--check")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_tune_cli_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "repo"
            shutil.copytree(
                REPO_ROOT,
                copy_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".aidlc", "*.pyc"),
            )

            # Switch governance mode to strict
            p_mode = run_script("scripts/tune.py", "--repo-root", str(copy_root), "set-mode", "strict")
            self.assertEqual(p_mode.returncode, 0, msg=p_mode.stderr)
            gates_md = (copy_root / "rules" / "gates.md").read_text(encoding="utf-8")
            self.assertIn("Active Mode**: `strict`", gates_md)

            # Update orchestration limits
            p_orch = run_script(
                "scripts/tune.py",
                "--repo-root",
                str(copy_root),
                "set-orchestration",
                "--max-depth",
                "2",
                "--max-parallel",
                "3",
                "--default-model",
                "flash",
                "--context-threshold-pct",
                "45",
                "--max-steps-handoff",
                "20",
            )
            self.assertEqual(p_orch.returncode, 0, msg=p_orch.stderr)
            gates_after = (copy_root / "rules" / "gates.md").read_text(encoding="utf-8")
            self.assertIn("`45%`", gates_after)
            self.assertIn("`>= 20`", gates_after)

            # Tune developer and verify prose preservation + frontmatter update
            dev_file = copy_root / "agents" / "developer.md"
            p_dev = run_script(
                "scripts/tune.py",
                "--repo-root",
                str(copy_root),
                "tune-agent",
                "developer",
                "--model",
                "pro",
                "--add-skill",
                "security-audit",
                "--instruction",
                "Always benchmark hot paths",
            )
            self.assertEqual(p_dev.returncode, 0, msg=p_dev.stderr)
            dev_text = dev_file.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(dev_text)
            assert fm is not None
            self.assertEqual(fm["model"], "pro")
            self.assertIn("skills/security-audit", fm["skills"])
            self.assertIn("Always benchmark hot paths", body)
            self.assertIn("Stay Inside Your Unit Boundary", body)

            # Disable an agent and check mainAgent/subagent become false
            p_dis = run_script(
                "scripts/tune.py",
                "--repo-root",
                str(copy_root),
                "tune-agent",
                "security",
                "--disable",
            )
            self.assertEqual(p_dis.returncode, 0, msg=p_dis.stderr)
            sec_fm, _ = parse_frontmatter((copy_root / "agents" / "security.md").read_text(encoding="utf-8"))
            assert sec_fm is not None
            self.assertIs(sec_fm["mainAgent"], False)
            self.assertIs(sec_fm["subagent"], False)

            # Create a brand new specialist agent
            p_create = run_script(
                "scripts/tune.py",
                "--repo-root",
                str(copy_root),
                "create-agent",
                "perf-auditor",
                "--description",
                "Profiles CPU and memory regressions in hot paths.",
                "--phase",
                "construction",
                "--model",
                "pro",
                "--skills",
                "code-review,systematic-debugging",
                "--tools",
                "read_file,run_command,send_message",
            )
            self.assertEqual(p_create.returncode, 0, msg=p_create.stderr)
            self.assertTrue((copy_root / "agents" / "perf-auditor.md").is_file())

            # Validate modified repo copy
            p_val = run_script("scripts/validate.py", "--repo-root", str(copy_root))
            self.assertEqual(p_val.returncode, 0, msg=p_val.stdout + p_val.stderr)

            # Reset back to defaults (note: perf-auditor is dropped from defaults so remove extra md first)
            (copy_root / "agents" / "perf-auditor.md").unlink()
            p_reset = run_script("scripts/tune.py", "--repo-root", str(copy_root), "reset")
            self.assertEqual(p_reset.returncode, 0, msg=p_reset.stderr)
            self.assertEqual(
                (copy_root / "config" / "config.json").read_text(encoding="utf-8"),
                (copy_root / "config" / "defaults.json").read_text(encoding="utf-8"),
            )

    def test_aidlc_state_gates_and_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "sample-app"
            proj.mkdir()

            # Balanced mode workflow with collision & gate checks
            p_init = run_script(
                "scripts/state.py",
                "init",
                "--project",
                str(proj),
                "--title",
                "Token Service",
                "--intent",
                "Add rotating JWT tokens",
                "--mode",
                "balanced",
            )
            self.assertEqual(p_init.returncode, 0, msg=p_init.stderr)

            p_tri = run_script(
                "scripts/state.py",
                "triage",
                "--project",
                str(proj),
                "--depth",
                "standard",
                "--rationale",
                "Security-sensitive multi-file auth feature",
            )
            self.assertEqual(p_tri.returncode, 0, msg=p_tri.stderr)

            # Register disjoint unit U1
            p_u1 = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U1",
                "--title",
                "Token issuer",
                "--owner",
                "developer",
                "--files",
                "src/auth/tokens.py,tests/test_tokens.py",
                "--skills",
                "tdd-implementation",
            )
            self.assertEqual(p_u1.returncode, 0, msg=p_u1.stderr)

            # Overlapping file in U2 must fail unless --allow-overlap
            p_u2_fail = run_script(
                "scripts/state.py",
                "register-unit",
                "--project",
                str(proj),
                "--id",
                "U2",
                "--title",
                "Token middleware",
                "--owner",
                "developer",
                "--files",
                "src/auth/tokens.py,src/auth/mw.py",
            )
            self.assertNotEqual(p_u2_fail.returncode, 0)
            self.assertIn("collision", p_u2_fail.stderr.lower())

            # Auto-approving inception -> construction in balanced mode must fail (requires human)
            p_gate1_fail = run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(proj),
                "--to",
                "construction",
                "--approved-by",
                "auto",
            )
            self.assertNotEqual(p_gate1_fail.returncode, 0)

            p_gate1_ok = run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(proj),
                "--to",
                "construction",
                "--approved-by",
                "human",
            )
            self.assertEqual(p_gate1_ok.returncode, 0, msg=p_gate1_ok.stderr)

            # Record peer handoff and check files created
            p_ho = run_script(
                "scripts/state.py",
                "record-handoff",
                "--project",
                str(proj),
                "--from",
                "developer",
                "--to",
                "verifier",
                "--phase",
                "construction",
                "--unit",
                "U1",
                "--status",
                "NEEDS_REVIEW",
                "--skills",
                "tdd-implementation",
                "--artifacts",
                "src/auth/tokens.py,tests/test_tokens.py",
                "--summary",
                "Implemented token rotation with 10 tests passing.",
            )
            self.assertEqual(p_ho.returncode, 0, msg=p_ho.stderr)
            self.assertTrue((proj / ".aidlc" / "handoffs" / "H001-developer-to-verifier.json").is_file())
            self.assertTrue((proj / ".aidlc" / "handoffs" / "H001-developer-to-verifier.md").is_file())

            # Advancing construction -> operation fails while U1 is pending
            p_gate2_incomplete = run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(proj),
                "--to",
                "operation",
                "--approved-by",
                "verifier",
            )
            self.assertNotEqual(p_gate2_incomplete.returncode, 0)

            p_upd = run_script(
                "scripts/state.py",
                "update-unit",
                "--project",
                str(proj),
                "--id",
                "U1",
                "--status",
                "approved",
            )
            self.assertEqual(p_upd.returncode, 0, msg=p_upd.stderr)

            p_gate2_ok = run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(proj),
                "--to",
                "operation",
                "--approved-by",
                "verifier",
            )
            self.assertEqual(p_gate2_ok.returncode, 0, msg=p_gate2_ok.stderr)

            # Strict mode check: fast-track cannot skip inception; verifier cannot clear construction->operation
            strict_proj = Path(tmp) / "strict-app"
            strict_proj.mkdir()
            self.assertEqual(
                run_script(
                    "scripts/state.py",
                    "init",
                    "--project",
                    str(strict_proj),
                    "--title",
                    "Strict Change",
                    "--mode",
                    "strict",
                ).returncode,
                0,
            )
            run_script(
                "scripts/state.py",
                "triage",
                "--project",
                str(strict_proj),
                "--depth",
                "fast-track",
                "--rationale",
                "Tiny typo",
            )
            strict_state = json.loads((strict_proj / ".aidlc" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(strict_state["phase"], "inception")

            # Autonomous mode check: auto clears inception -> construction
            auto_proj = Path(tmp) / "auto-app"
            auto_proj.mkdir()
            run_script(
                "scripts/state.py",
                "init",
                "--project",
                str(auto_proj),
                "--title",
                "Auto Feature",
                "--mode",
                "autonomous",
                "--depth",
                "standard",
            )
            p_auto = run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(auto_proj),
                "--to",
                "construction",
                "--approved-by",
                "auto",
            )
            self.assertEqual(p_auto.returncode, 0, msg=p_auto.stderr)

    def test_install_and_uninstall_all_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # 1. Antigravity user-scope (copy) & project-scope (symlink)
            agy_user_dir = root / "agy_plugins"
            p_agy_u = run_script(
                "scripts/install.py",
                "antigravity",
                "--target-dir",
                str(agy_user_dir),
                "--method",
                "copy",
            )
            self.assertEqual(p_agy_u.returncode, 0, msg=p_agy_u.stderr)
            installed_plugin = agy_user_dir / "agent-skills"
            self.assertTrue((installed_plugin / "plugin.json").is_file())
            self.assertFalse((installed_plugin / "tests").exists())
            self.assertEqual(
                run_script("scripts/install.py", "antigravity", "--target-dir", str(agy_user_dir), "--uninstall").returncode,
                0,
            )
            self.assertFalse(installed_plugin.exists())

            agy_proj = root / "agy_proj"
            agy_proj.mkdir()
            p_agy_p = run_script(
                "scripts/install.py",
                "antigravity",
                "--scope",
                "project",
                "--project",
                str(agy_proj),
                "--method",
                "symlink",
            )
            self.assertEqual(p_agy_p.returncode, 0, msg=p_agy_p.stderr)
            self.assertTrue((agy_proj / ".agents" / "plugins" / "agent-skills").is_symlink())
            run_script(
                "scripts/install.py",
                "antigravity",
                "--scope",
                "project",
                "--project",
                str(agy_proj),
                "--uninstall",
            )
            self.assertFalse((agy_proj / ".agents" / "plugins" / "agent-skills").exists())

            # 2. Claude Code translation check
            claude_dir = root / "claude_home"
            p_cc = run_script(
                "scripts/install.py",
                "claude-code",
                "--target-dir",
                str(claude_dir),
                "--method",
                "copy",
            )
            self.assertEqual(p_cc.returncode, 0, msg=p_cc.stderr)
            self.assertTrue((claude_dir / "skills" / "workflow" / "SKILL.md").is_file())
            self.assertTrue((claude_dir / "rules" / "aidlc.md").is_file())
            cc_dev_fm, _ = parse_frontmatter((claude_dir / "agents" / "developer.md").read_text(encoding="utf-8"))
            assert cc_dev_fm is not None
            self.assertNotIn("mainAgent", cc_dev_fm)
            self.assertNotIn("subagent", cc_dev_fm)
            self.assertIn("Read", cc_dev_fm["tools"])
            self.assertIn("Bash", cc_dev_fm["tools"])
            self.assertIn("Agent", cc_dev_fm["tools"])
            run_script("scripts/install.py", "claude-code", "--target-dir", str(claude_dir), "--uninstall")
            self.assertFalse((claude_dir / "skills" / "workflow").exists())
            self.assertFalse((claude_dir / "agents" / "developer.md").exists())

            # 3. Cursor project export (.mdc rules + skills + agents)
            cursor_proj = root / "cursor_proj"
            cursor_proj.mkdir()
            p_cur = run_script("scripts/install.py", "cursor", "--project", str(cursor_proj))
            self.assertEqual(p_cur.returncode, 0, msg=p_cur.stderr)
            self.assertTrue((cursor_proj / ".cursor" / "rules" / "core.mdc").is_file())
            self.assertTrue((cursor_proj / ".cursor" / "rules" / "gates.mdc").is_file())
            self.assertTrue((cursor_proj / ".cursor" / "skills" / "tdd-implementation" / "SKILL.md").is_file())
            run_script("scripts/install.py", "cursor", "--project", str(cursor_proj), "--uninstall")
            self.assertFalse((cursor_proj / ".cursor" / "rules" / "core.mdc").exists())

            # 4. Codex managed AGENTS.md block preservation + clean uninstall
            codex_dir = root / "codex_home"
            codex_dir.mkdir()
            existing_agents = codex_dir / "AGENTS.md"
            existing_agents.write_text("# My Custom Codex Rules\n\nAlways keep tests fast.\n", encoding="utf-8")
            p_cdx = run_script("scripts/install.py", "codex", "--target-dir", str(codex_dir))
            self.assertEqual(p_cdx.returncode, 0, msg=p_cdx.stderr)
            updated_text = existing_agents.read_text(encoding="utf-8")
            self.assertIn("# My Custom Codex Rules", updated_text)
            self.assertIn(CODEX_START_MARKER, updated_text)
            self.assertIn(CODEX_END_MARKER, updated_text)

            run_script("scripts/install.py", "codex", "--target-dir", str(codex_dir), "--uninstall")
            reverted_text = existing_agents.read_text(encoding="utf-8")
            self.assertIn("# My Custom Codex Rules", reverted_text)
            self.assertNotIn(CODEX_START_MARKER, reverted_text)

    def test_hook_gate_guard_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "hook_proj"
            proj.mkdir()
            run_script(
                "scripts/state.py",
                "init",
                "--project",
                str(proj),
                "--title",
                "Hook Test",
                "--mode",
                "strict",
                "--depth",
                "standard",
            )

            # SessionStart injects context
            p_start = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "SessionStart",
                        "cwd": str(proj),
                        "workspacePaths": [str(proj)],
                    }
                ),
            )
            self.assertEqual(p_start.returncode, 0)
            out_start = json.loads(p_start.stdout)
            self.assertIn("injectSteps", out_start)
            self.assertIn("Hook Test", out_start["injectSteps"][0]["userMessage"])

            # PreToolUse in strict+inception outside .aidlc/ returns ask
            p_ask = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreToolUse",
                        "cwd": str(proj),
                        "toolCall": {
                            "id": "t1",
                            "name": "edit_file",
                            "args": {"Path": str(proj / "src" / "app.py")},
                        },
                    }
                ),
            )
            self.assertEqual(p_ask.returncode, 0)
            self.assertEqual(json.loads(p_ask.stdout).get("decision"), "ask")

            # PreToolUse inside .aidlc/ is allowed ({})
            p_aidlc = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreToolUse",
                        "cwd": str(proj),
                        "toolCall": {
                            "id": "t2",
                            "name": "write_file",
                            "args": {"Path": str(proj / ".aidlc" / "inception" / "design.md")},
                        },
                    }
                ),
            )
            self.assertEqual(p_aidlc.returncode, 0)
            self.assertEqual(json.loads(p_aidlc.stdout), {})

            # Advance to construction -> edits outside .aidlc/ return {}
            run_script(
                "scripts/state.py",
                "advance",
                "--project",
                str(proj),
                "--to",
                "construction",
                "--approved-by",
                "human",
            )
            p_constr = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreToolUse",
                        "cwd": str(proj),
                        "toolCall": {
                            "id": "t3",
                            "name": "edit_file",
                            "args": {"Path": str(proj / "src" / "app.py")},
                        },
                    }
                ),
            )
            self.assertEqual(p_constr.returncode, 0)
            self.assertEqual(json.loads(p_constr.stdout), {})

            # PreInvocation below 50% threshold / steps returns {}
            small_transcript = Path(tmp) / "small_transcript.jsonl"
            small_transcript.write_text("x" * 1000, encoding="utf-8")
            p_pre_ok = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreInvocation",
                        "cwd": str(proj),
                        "initialNumSteps": 5,
                        "transcriptPath": str(small_transcript),
                    }
                ),
            )
            self.assertEqual(p_pre_ok.returncode, 0)
            self.assertEqual(json.loads(p_pre_ok.stdout), {})

            # PreInvocation at >= 25 steps triggers 50% context rotation systemMessage
            p_pre_steps = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreInvocation",
                        "cwd": str(proj),
                        "initialNumSteps": 25,
                        "transcriptPath": str(small_transcript),
                    }
                ),
            )
            self.assertEqual(p_pre_steps.returncode, 0)
            out_steps = json.loads(p_pre_steps.stdout)
            self.assertIn("CONTEXT ROTATION GUARD", out_steps["injectSteps"][0]["systemMessage"]["systemMessage"])

            # PreInvocation with transcript >= 50% of 200k token budget (~400KB) triggers rotation
            big_transcript = Path(tmp) / "big_transcript.jsonl"
            big_transcript.write_text("x" * 420000, encoding="utf-8")
            p_pre_size = run_script(
                "scripts/hooks/gate_guard.py",
                stdin_text=json.dumps(
                    {
                        "hookEventName": "PreInvocation",
                        "cwd": str(proj),
                        "initialNumSteps": 3,
                        "transcriptPath": str(big_transcript),
                    }
                ),
            )
            self.assertEqual(p_pre_size.returncode, 0)
            out_size = json.loads(p_pre_size.stdout)
            self.assertIn("CONTEXT ROTATION GUARD", out_size["injectSteps"][0]["systemMessage"]["systemMessage"])

            # Malformed stdin fails open cleanly
            p_bad = run_script("scripts/hooks/gate_guard.py", stdin_text="{not valid json")
            self.assertEqual(p_bad.returncode, 0)
            self.assertEqual(json.loads(p_bad.stdout), {})


if __name__ == "__main__":
    unittest.main()
