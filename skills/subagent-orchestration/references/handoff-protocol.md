# Inter-Agent Handoff Envelope Protocol

All peer-to-peer prompts (`send_message`), Swarm posts, and subagent completion summaries follow one deterministic envelope so receiving agents act without re-reading the entire workspace.

## Standard Handoff Envelope

```markdown
### HANDOFF [<UNIT_ID or PHASE>] <STATUS>
- **From**: `<sender-agent-name>`
- **To**: `<recipient-agent-name>`
- **Phase**: `<inception | construction | operation>`
- **Skills Used**: `<skill-1, skill-2>`
- **Artifacts**: `<comma-separated file paths>`
- **Verification**: `<exact command(s) run and pass/fail count, or N/A>`

#### Summary
<2-5 crisp sentences describing what was completed, discovered, or changed.>

#### Open Findings / Next Action
- <Concrete next step or numbered CRITICAL/HIGH/MEDIUM/LOW findings with file:line.>
```

## Valid Status Transitions

| Status | Meaning | Expected Next Peer |
| :--- | :--- | :--- |
| `READY` | Input context or fix is ready for consumption | Target worker or `orchestrator` |
| `NEEDS_REVIEW` | Unit implementation and unit tests pass; awaiting review | `verifier` (and `security` if sensitive) |
| `CHANGES_REQUESTED` | Reviewer found blocking `CRITICAL`/`HIGH` issues or failing checks | Author (`developer` or `architect`) |
| `APPROVED` | All checks and review criteria satisfied | `orchestrator` / `operator` |
| `BLOCKED` | External dependency, missing permission, or design contradiction | `orchestrator` (escalate to `architect` or human) |

## Peer-to-Peer Iteration Rules

1. **Direct Peer Loops**: When `orchestrator` starts an author and verifier together, give the author the verifier's `conversationId` (or Swarm name `@verifier`) so fixes iterate directly (`NEEDS_REVIEW` <-> `CHANGES_REQUESTED`) without waking the orchestrator on every round.
2. **Escalation Cap**: If `CHANGES_REQUESTED` repeats beyond `orchestration.max_review_rounds` (default `3`), send `BLOCKED` to `orchestrator` for human or architect intervention.
3. **Ledger Recording**: Record key handoffs persistently:
   ```bash
   python3 scripts/state.py record-handoff \
     --project <project> \
     --from developer \
     --to verifier \
     --phase construction \
     --unit U1 \
     --status NEEDS_REVIEW \
     --skills tdd-implementation \
     --artifacts src/auth.py,tests/test_auth.py \
     --summary "Implemented token rotation unit with 14 passing unit tests."
   ```
