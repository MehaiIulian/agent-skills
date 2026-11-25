# Requirements Specification (`.aidlc/inception/requirements.md`)

## 1. Business Rules & Domain Policies

| ID | Status (`Existing` / `New` / `Updated`) | Business Rule / Invariant | Enforcement & Violation Behavior |
| :--- | :--- | :--- | :--- |
| BR-1 | `<Existing \| New>` | `<domain policy, state transition rule, or invariant>` | `<where enforced + error/rejection when violated>` |

## 2. Functional Requirements

| ID | Requirement | Linked Business Rules | Priority | Acceptance Criteria (Given / When / Then) |
| :--- | :--- | :--- | :--- | :--- |
| FR-1 | `<capability>` | `BR-1` | Must | **Given** ... **When** ... **Then** ... |

## 3. Non-Functional Requirements (NFRs)

- **Security / Auth**: <boundaries, input validation, least privilege>
- **Performance / Scale**: <latency, throughput, resource bounds>
- **Reliability / Error Handling**: <timeouts, retries, failure modes>
- **Compatibility**: <supported OS/runtimes/APIs>

## 4. Open Questions Resolved

| Question | Decision | Decided By |
| :--- | :--- | :--- |
| `<question>` | `<decision>` | `<human / architect>` |

## 5. Explicit Non-Goals

- <Explicitly excluded scope>
