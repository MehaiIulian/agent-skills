---
name: security-audit
description: >-
  Conduct threat modeling (STRIDE-lite) and security code/configuration audits
  to uncover vulnerabilities, secret leaks, injection flaws, and trust-boundary
  gaps. Use during deep Inception design review or Construction security gates.
license: MIT
metadata:
  phase: construction
  category: security
  version: "1.0.0"
---

# Threat Modeling & Security Audit (AI-DLC Security)

Identify realistic security risks across designs, code, dependencies, and runtime configurations before changes ship.

## Step 1: Map Trust Boundaries & Assets (STRIDE-lite)

1. Identify untrusted inputs (HTTP/API payloads, CLI flags, file paths, environment vars, webhook/hook stdin, LLM/tool outputs).
2. Identify high-value assets (credentials, user data, auth tokens, writeable filesystems, shell execution paths).
3. Check trust boundaries for: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege.

## Step 2: Inspect Code, Configs & Dependencies

Audit changes against [references/owasp-checklist.md](references/owasp-checklist.md):
- Run available static/dependency scanners (`pip-audit`, `npm audit`, `bandit`, `semgrep`, `gitleaks`, etc.) if installed in the project environment.
- Manually trace tainted inputs from entry point to sink (`subprocess`, SQL, file paths, templates, deserializers).

## Step 3: Report & Gate

For every verified issue, output:
- **Severity**: `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`
- **Location**: exact `file:line`
- **Attack Scenario**: concrete exploitability path (no speculative filler)
- **Remediation**: specific, testable fix

Gate rule:
- Any unresolved `CRITICAL` or `HIGH` finding -> **`CHANGES_REQUESTED`** sent directly to `developer` / `architect` via `send_message` and escalated to `orchestrator`.
- Zero `CRITICAL`/`HIGH` findings -> **`APPROVED`** (noting any `MEDIUM`/`LOW` advisories).
