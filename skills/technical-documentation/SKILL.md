---
name: technical-documentation
description: >-
  Author and verify accurate READMEs, architecture docs, API references,
  changelogs, and operational runbooks grounded strictly in observed codebase
  files and executed commands. Use during AI-DLC Operation or when documenting
  new capabilities.
license: MIT
metadata:
  phase: operation
  category: documentation
  version: "1.0.0"
---

# Truthful Technical Documentation

Documentation must match the actual codebase and verified commands—stale docs are worse than missing docs.

## Core Rule

**Never document an unverified file path, CLI flag, config field, or example output.** Check every symbol and run (or dry-run) every documented command against the current repo.

## Step 1: Identify Doc Impact

Inspect changed interfaces, CLI subcommands, config schemas, environment variables, and error behaviors across:
- `README.md` (quickstart, installation, core workflows)
- Architecture & customization docs (`docs/*.md`)
- API / schema / changelog / migration notes

## Step 2: Write Crisp, Scannable Docs

1. Lead with **working quickstart commands** and minimal copy-pasteable examples.
2. Use clickable relative Markdown links to real files and tables for options/configs.
3. Document defaults, prerequisites, failure modes, and troubleshooting steps explicitly.
4. When illustrating workflows or component relationships, add a compact Mermaid diagram (`flowchart TD` / `LR` or `sequenceDiagram` with quoted special-character labels).

## Step 3: Verify Every Claim

- Confirm every linked file path exists (`ls` / `read_file`).
- Run documented CLI `--help`, validator, and smoke commands to ensure flags and behavior match word-for-word.
- Report exact checks executed in your Handoff Envelope to `operator` / `orchestrator`.
