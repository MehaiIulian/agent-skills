---
name: git-pr-workflow
description: >-
  Manage safe Git branching, atomic conventional commits, diff and secret
  self-audits, and structured Pull Request summaries linked to AI-DLC specs
  and test evidence. Use when preparing commits or pull requests.
license: MIT
metadata:
  phase: operation
  category: collaboration
  version: "1.0.0"
---

# Git & Pull Request Workflow

Keep version control history clean, atomic, secret-free, and directly traceable to AI-DLC specs and verification evidence.

## Step 1: Audit Working Tree Before Staging

1. Run `git status` and `git diff` to verify only intended files are modified (no temp artifacts, debug logs, `.aidlc/` runtime scratch if gitignored, or accidental edits outside unit scope).
2. Scan staged/unstaged diffs for secrets, API keys, local absolute user paths, or unintended binary files.
3. Confirm all tests and validators pass **after** the final edit.

## Step 2: Atomic Branching & Conventional Commits

- Create focused branches (`feat/<slug>`, `fix/<slug>`, `refactor/<slug>`, `docs/<slug>`) when not already on a task branch.
- Group cohesive changes into atomic commits using Conventional Commits:
  `<type>(<scope>): <imperative summary>` (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`).
- Never use destructive git flags (`reset --hard`, `push --force`, `clean -fd`) without explicit user authorization.

## Step 3: Draft Evidence-Backed PR Summary

Include in the PR description:
1. **Why & What**: Link to `.aidlc/inception/requirements.md` / design summary and bulleted behavioral changes.
2. **Verification Evidence**: Exact commands executed (`pytest`, `unittest`, `validate.py`, linters) with observed counts.
3. **Review & Security Status**: Reference `verifier` / `security` sign-off and any follow-ups.
4. **Operational Notes**: Migrations, config changes, or rollback steps if applicable.
