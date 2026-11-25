# Security Audit Checklist (OWASP & Supply-Chain)

## Input Validation & Injection
- [ ] SQL/NoSQL queries use parameterization; never string interpolation.
- [ ] Shell invocations avoid `shell=True` with untrusted inputs; pass argument lists cleanly.
- [ ] File paths from external input are normalized and validated against a base directory (`resolve().relative_to(base)`) to block path traversal (`../`) and symlink escapes.
- [ ] URLs fetched server-side validate scheme/host and block internal metadata/loopback IP ranges (SSRF).

## Authentication, Authorization & Sessions
- [ ] Authn checks and object-level authz (ownership/tenant checks) run server-side on every protected endpoint/command.
- [ ] Constant-time comparisons (`hmac.compare_digest`) are used for signatures/tokens.
- [ ] Tokens/cookies enforce tight scopes, expiration, and secure transport flags.

## Secrets, Cryptography & Deserialization
- [ ] Zero hardcoded secrets, API keys, private keys, or credentials in code, tests, or git history.
- [ ] Modern algorithms only (AES-GCM/ChaCha20, SHA-256+, Argon2/bcrypt/scrypt); no `MD5`/`SHA1`/ECB for security.
- [ ] Safe parsing only (`json.loads`, `yaml.safe_load`); never `pickle.loads` or `eval` on untrusted data.

## Supply Chain & Least Privilege
- [ ] CI/workflows, hooks, and agents follow least-privilege permissions and sandbox boundaries.
- [ ] No unpinned or typosquatted dependencies; lockfiles updated cleanly.
