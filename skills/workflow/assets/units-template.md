# Units of Work Breakdown (`.aidlc/inception/units.md`)

Design-only `architect` authors this table with disjoint file ownership per wave; `orchestrator` (or any agent with `run_command`) registers each active unit via `scripts/state.py register-unit`.

| Unit ID | Wave | Title | Owner | Owned Files (Disjoint per Wave) | Dependencies (`depends_on`) | Required Skills | Linked Rules & Criteria (`BR-*` / `FR-*` / `NFR-*`) |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| U1 | 1 | `<unit title>` | `developer` | `src/mod_a.py, tests/test_mod_a.py` | None | `tdd-implementation` | `BR-1, FR-1` |
| U2 | 2 | `<unit title>` | `developer` | `src/mod_b.py, tests/test_mod_b.py` | `U1` | `tdd-implementation` | `BR-2, FR-2, NFR-1` |

