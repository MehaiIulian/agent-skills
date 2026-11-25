# Code Review Checklist

## Correctness & Contracts
- [ ] Every `FR-*` and `NFR-*` mapped to this unit is implemented and tested.
- [ ] Boundary values (empty inputs, `0`, negative counts, Unicode, large inputs, `None`/`null`) are handled explicitly.
- [ ] Public interfaces, CLI flags, and schemas match `.aidlc/inception/design.md`.
- [ ] Return types and error codes are consistent across callers and callees.

## State, Concurrency & Resource Safety
- [ ] File handles, DB connections, sockets, and temp artifacts are deterministically closed/cleaned up.
- [ ] Shared mutable state, file writes, or concurrent workers avoid race conditions and non-atomic partial writes.
- [ ] External calls (network, subprocesses) enforce explicit timeouts and bounded retries.

## Error Handling & Observability
- [ ] Errors are never swallowed silently (`except Exception: pass`); contextual errors propagate or fail loudly.
- [ ] Logs and error messages omit secrets, tokens, and raw PII.

## Tests & Maintainability
- [ ] Automated tests actually fail when the production logic breaks (no tautological mocks or skipped assertions).
- [ ] No duplicated blocks that belong in a shared parameterized helper.
- [ ] Functions are concise, readable, and avoid gratuitous changes outside unit ownership.
