# Units of Work Breakdown

Register every active unit with disjoint file ownership using `scripts/state.py register-unit`.

| Unit ID | Title | Owner | Owned Files (Disjoint) | Dependencies | Required Skills | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| U1 | `<unit title>` | `developer` | `src/mod_a.py, tests/test_mod_a.py` | None | `tdd-implementation` | `<FR/NFR IDs>` |
| U2 | `<unit title>` | `developer` | `src/mod_b.py, tests/test_mod_b.py` | U1 | `tdd-implementation` | `<FR/NFR IDs>` |
