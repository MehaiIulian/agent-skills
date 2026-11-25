# Operation Release Readiness Checklist (`.aidlc/operation/release-checklist.md`)

- **Release / PR Title**: `<title>`
- **Prepared By**: `operator`
- **Verification Verdict**: `<APPROVED>`

## Checklist

- [ ] All Construction work units are `approved` in `.aidlc/state.json`.
- [ ] Full test suite and static validators pass after the final edit (exact command outputs attached).
- [ ] Security audit checks completed (or marked N/A for non-sensitive `fast-track` change).
- [ ] Documentation (`README.md`, API references, changelogs, runbooks) verified against actual code paths.
- [ ] Backward-compatibility, migrations, and rollback steps documented below.

## Rollback Plan

1. `<Exact step to revert safely (e.g., git revert, feature flag toggle, schema down-migration).>`

## Summary for Human Sign-Off

- **Changed Files**: `<list>`
- **Residual Risks**: `<any known caveats or follow-ups>`
