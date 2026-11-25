#!/usr/bin/env python3
"""Zero-dependency YAML frontmatter and managed Markdown block utilities."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

VALID_ANTIGRAVITY_TOOLS = (
    "read_file",
    "edit_file",
    "write_file",
    "run_command",
    "manage_task",
    "search_web",
    "ask_question",
    "define_subagent",
    "invoke_subagent",
    "send_message",
    "manage_subagents",
    "run_workflow",
    "swarm",
    "schedule",
)
VALID_ANTIGRAVITY_TOOLS_SET = set(VALID_ANTIGRAVITY_TOOLS)

VALID_MODELS = ("inherit", "flash_lite", "flash", "pro")
VALID_MODELS_SET = set(VALID_MODELS)

VALID_EXEC_POLICIES = ("off", "auto", "eager", "sandbox")
VALID_EXEC_POLICIES_SET = set(VALID_EXEC_POLICIES)

RESERVED_AGENT_NAMES = frozenset(
    {"self", "browser", "research", "deepagent", "review-agent", "image-generator"}
)

KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

TUNING_START_MARKER = "<!-- AIDLC:TUNING:START -->"
TUNING_END_MARKER = "<!-- AIDLC:TUNING:END -->"
CODEX_START_MARKER = "<!-- AIDLC:CODEX:START -->"
CODEX_END_MARKER = "<!-- AIDLC:CODEX:END -->"


class FrontmatterError(ValueError):
    """Raised when YAML frontmatter cannot be parsed cleanly."""


def _parse_scalar(raw: str) -> Any:
    val = raw.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        inner = val[1:-1]
        if val.startswith('"'):
            inner = (
                inner.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\\\", "\\")
            )
        return inner
    lower = val.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "~"):
        return None
    if re.fullmatch(r"-?[0-9]+", val):
        return int(val)
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_inline_list(inner)]
    return val


def _split_inline_list(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    escaped = False
    for ch in text:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\" and quote == '"':
            buf.append(ch)
            escaped = True
            continue
        if ch in ('"', "'"):
            if quote is None:
                quote = ch
            elif quote == ch:
                quote = None
            buf.append(ch)
            continue
        if ch == "," and quote is None:
            parts.append("".join(buf).strip())
            buf.clear()
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse leading YAML frontmatter (`--- ... ---`) and return (data, body).

    Returns (None, text) when the document does not start with frontmatter.
    Raises FrontmatterError if frontmatter opens with `---` but is malformed.
    """
    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, normalized

    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise FrontmatterError("Unclosed YAML frontmatter delimiter '---'")

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :])
    if body.startswith("\n"):
        body = body[1:]

    data: dict[str, Any] = {}
    i = 0
    while i < len(fm_lines):
        raw_line = fm_lines[i]
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if raw_line.startswith(" ") or raw_line.startswith("\t"):
            raise FrontmatterError(f"Unexpected indentation in frontmatter: {raw_line!r}")
        if ":" not in raw_line:
            raise FrontmatterError(f"Invalid frontmatter line (missing ':'): {raw_line!r}")

        key, rest = raw_line.split(":", 1)
        key = key.strip()
        rest_stripped = rest.strip()

        if rest_stripped in (">-", ">", "|-", "|"):
            fold = rest_stripped.startswith(">")
            block_lines: list[str] = []
            i += 1
            while i < len(fm_lines):
                nxt = fm_lines[i]
                if nxt.strip() == "":
                    block_lines.append("")
                    i += 1
                    continue
                if nxt.startswith(" ") or nxt.startswith("\t"):
                    block_lines.append(nxt.lstrip(" \t"))
                    i += 1
                    continue
                break
            while block_lines and block_lines[-1] == "":
                block_lines.pop()
            if fold:
                paragraphs: list[str] = []
                cur: list[str] = []
                for bl in block_lines:
                    if bl == "":
                        if cur:
                            paragraphs.append(" ".join(cur))
                            cur = []
                    else:
                        cur.append(bl)
                if cur:
                    paragraphs.append(" ".join(cur))
                data[key] = "\n\n".join(paragraphs)
            else:
                data[key] = "\n".join(block_lines)
            continue

        if rest_stripped == "":
            # Expect nested block: list (`  - item`) or 1-level map (`  subkey: val`)
            items: list[Any] = []
            mapping: dict[str, Any] = {}
            mode: str | None = None
            i += 1
            while i < len(fm_lines):
                nxt = fm_lines[i]
                nxt_stripped = nxt.strip()
                if not nxt_stripped or nxt_stripped.startswith("#"):
                    i += 1
                    continue
                if not (nxt.startswith(" ") or nxt.startswith("\t")):
                    break
                if nxt_stripped.startswith("- "):
                    if mode == "map":
                        raise FrontmatterError(f"Mixed map and list under key '{key}'")
                    mode = "list"
                    items.append(_parse_scalar(nxt_stripped[2:]))
                elif ":" in nxt_stripped:
                    if mode == "list":
                        raise FrontmatterError(f"Mixed list and map under key '{key}'")
                    mode = "map"
                    sub_k, sub_v = nxt_stripped.split(":", 1)
                    mapping[sub_k.strip()] = _parse_scalar(sub_v)
                else:
                    raise FrontmatterError(f"Invalid nested frontmatter line under '{key}': {nxt!r}")
                i += 1
            if mode == "map":
                data[key] = mapping
            else:
                data[key] = items
            continue

        data[key] = _parse_scalar(rest_stripped)
        i += 1

    return data, body


def _format_scalar(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if val is None:
        return "null"
    s = str(val)
    needs_quotes = (
        s == ""
        or s[0] in ("-", "?", ":", "[", "]", "{", "}", "#", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`", " ")
        or s[-1] == " "
        or ": " in s
        or " #" in s
        or s.lower() in ("true", "false", "null", "yes", "no")
        or "\n" in s
    )
    if needs_quotes:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return s


def dump_frontmatter(data: dict[str, Any]) -> str:
    """Serialize a mapping into a YAML frontmatter block ending with `---\\n`."""
    lines = ["---"]
    for key, val in data.items():
        if isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {_format_scalar(item)}")
        elif isinstance(val, dict):
            if not val:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for sub_k, sub_v in val.items():
                    lines.append(f"  {sub_k}: {_format_scalar(sub_v)}")
        elif isinstance(val, str) and len(val) > 88 and "\n" not in val:
            lines.append(f"{key}: >-")
            words = val.split()
            cur_line = " "
            for w in words:
                if len(cur_line) + len(w) + 1 > 78 and len(cur_line) > 2:
                    lines.append(cur_line)
                    cur_line = f"  {w}"
                elif cur_line == " ":
                    cur_line = f"  {w}"
                else:
                    cur_line += f" {w}"
            if cur_line.strip():
                lines.append(cur_line)
        else:
            lines.append(f"{key}: {_format_scalar(val)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def replace_managed_block(
    text: str, start_marker: str, end_marker: str, inner_content: str
) -> str:
    """Replace content between markers, preserving everything outside them."""
    normalized = text.replace("\r\n", "\n")
    replacement = f"{start_marker}\n{inner_content.rstrip()}\n{end_marker}"
    start_idx = normalized.find(start_marker)
    end_idx = normalized.find(end_marker)
    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        end_after = end_idx + len(end_marker)
        return normalized[:start_idx] + replacement + normalized[end_after:]
    sep = "\n\n" if normalized and not normalized.endswith("\n\n") else ""
    if normalized.endswith("\n") and not normalized.endswith("\n\n"):
        sep = "\n"
    return f"{normalized.rstrip()}{sep}{replacement}\n"


def remove_managed_block(text: str, start_marker: str, end_marker: str) -> str:
    """Remove a managed block (inclusive of markers) from text cleanly."""
    normalized = text.replace("\r\n", "\n")
    start_idx = normalized.find(start_marker)
    end_idx = normalized.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        return normalized
    before = normalized[:start_idx].rstrip()
    after = normalized[end_idx + len(end_marker) :].lstrip("\n")
    if before and after:
        return f"{before}\n\n{after}"
    if before:
        return f"{before}\n"
    return after


def discover_skills(repo_root: Path) -> set[str]:
    """Return all skill folder names under <repo_root>/skills/<name>/SKILL.md."""
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return set()
    return {
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir() and (entry / "SKILL.md").is_file()
    }
