# AI-DLC Phases, Governance Modes, and Gate Matrix

## Governance Mode Behavior

| Transition | `strict` | `balanced` (Default) | `autonomous` |
| :--- | :--- | :--- | :--- |
| `triage -> construction` (fast-track) | **Disallowed** (must pass Inception) | Allowed for low-risk 1-2 file fixes | Allowed for low-risk 1-2 file fixes |
| `inception -> construction` | `human` approval required | `human` approval required | `auto` (self-verified against spec completeness) |
| `construction -> operation` | `human` approval + verifier pass | `verifier` (`verifier` sign-off; `human` optional) | `verifier` (`verifier` sign-off required) |
| `operation -> completed` | `human` approval required | `human` approval required | `auto` (if zero blockers; pauses only on blockers) |

## Required Artifacts by Depth

| Depth | `.aidlc/inception/` | `.aidlc/construction/` | `.aidlc/operation/` |
| :--- | :--- | :--- | :--- |
| `fast-track` | Optional intent note | Unit test output + diff verification | Concise summary |
| `standard` | `requirements.md`, `design.md`, registered units | Unit TDD runs + `verification-report.md` | `release-checklist.md` + updated docs |
| `deep` | `intent.md`, `requirements.md`, `design.md` + ADRs, threat model | Unit TDD runs + `verification-report.md` + security audit | `release-checklist.md` + rollback plan + runbook |

## Mandatory Re-Plan / Escalation Triggers

Stop Construction and escalate back to Inception (`architect`) or the human user whenever:
1. A unit's implementation requires changing files owned by another active unit or breaks an approved interface contract.
2. Verification fails after `orchestration.max_review_rounds` peer-review cycles.
3. A `CRITICAL` security vulnerability invalidates the chosen design or trust boundary.
4. Discovered codebase behavior contradicts a key assumption in `.aidlc/inception/design.md`.
