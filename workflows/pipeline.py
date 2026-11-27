"""Dynamic Antigravity run_workflow pipeline for the AI-DLC lifecycle.

Invoke via Antigravity's `run_workflow` tool, optionally passing Args:
  {
    "intent": "Describe the feature, refactor, or fix to deliver",
    "depth": "standard",          # "fast-track" | "standard" | "deep"
    "parallel_units": true,       # true -> parallel share workspaces for >1 units
    "run_security": true,         # true -> run security alongside verifier
    "max_review_rounds": 2        # max verifier/fix iterations
  }
"""

intent = args.get("intent", "Implement the requested change following AI-DLC.")
depth = args.get("depth", "standard")
parallel_units = bool(args.get("parallel_units", True))
run_security = bool(args.get("run_security", True))
max_review_rounds = int(args.get("max_review_rounds", 2))
workspace_root = WORKSPACES[0] if WORKSPACES else "."

UNIT_ITEM_SCHEMA = {
    "type": "object",
    "required": ["id", "title", "files", "depends_on", "acceptance_criteria", "skills"],
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "files": {"type": "array", "items": {"type": "string"}},
        "depends_on": {"type": "array", "items": {"type": "string"}},
        "acceptance_criteria": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
    },
}

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "required": ["summary", "business_rules", "design_doc", "units"],
    "properties": {
        "summary": {"type": "string"},
        "business_rules": {"type": "array", "items": {"type": "string"}},
        "design_doc": {"type": "string"},
        "units": {"type": "array", "items": UNIT_ITEM_SCHEMA, "minItems": 1},
    },
}

DEV_RESULT_SCHEMA = {
    "type": "object",
    "required": ["unit_id", "summary", "files_changed", "test_results"],
    "properties": {
        "unit_id": {"type": "string"},
        "summary": {"type": "string"},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "test_results": {"type": "string"},
    },
}

REVIEW_RESULT_SCHEMA = {
    "type": "object",
    "required": ["approved", "findings", "summary"],
    "properties": {
        "approved": {"type": "boolean"},
        "findings": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
}

phase("Inception — Research & Architecture")
log(f"Workspace: {workspace_root} | Depth: {depth} | Intent: {intent}")

research_brief = await agent(
    prompt=(
        f"Map the repository at {workspace_root} for this AI-DLC intent:\n"
        f"{intent}\n\n"
        "Read skills/requirements-discovery/SKILL.md. Return a concise read-only brief "
        "covering relevant files, existing architecture/helpers, test commands, and risks."
    ),
    schema={"type": "string"},
    role="AI-DLC Researcher",
    type_name="researcher",
    workspace="inherit",
)
log("Research brief ready.")

plan = await agent(
    prompt=(
        f"Intent: {intent}\nDepth: {depth}\n\n"
        f"Repository research brief:\n{research_brief}\n\n"
        "Read skills/requirements-discovery/SKILL.md, skills/architecture-ddd/SKILL.md, "
        "and skills/task-decomposition/SKILL.md. "
        "Inventory existing and new Business Rules (BR-*), design the solution with depth-scaled C4 diagrams, "
        "and split work into disjoint-file Units of Work with explicit depends_on wave ordering. "
        "Write ONLY inside .aidlc/inception/ (requirements.md, design.md, units.md when depth != 'fast-track'; "
        "record conservative assumptions instead of calling ask_question in headless workflow mode). "
        "Return structured JSON matching the schema."
    ),
    schema=ARCHITECTURE_SCHEMA,
    role="AI-DLC Architect",
    type_name="architect",
    workspace="inherit",
)
log(f"Architecture plan ready with {len(plan['units'])} unit(s): {plan['summary']}")

phase("Construction — Implementation")
business_rules_block = "\n".join(f"- {br}" for br in plan.get("business_rules", [])) or "- (see design_doc)"


def _norm_unit_path(raw_path):
    cleaned = raw_path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/")
    parts = []
    for part in cleaned.split("/"):
        if not part or part == ".":
            continue
        if part == ".." and parts and parts[-1] != "..":
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _wave_has_file_overlap(wave_units):
    seen = set()
    for unit in wave_units:
        normed = {_norm_unit_path(f) for f in unit.get("files", []) if _norm_unit_path(f)}
        if seen & normed:
            return True
        seen |= normed
    return False


def _compute_unit_waves(units):
    remaining = list(units)
    known_ids = {u["id"] for u in remaining}
    completed = set()
    waves = []
    while remaining:
        ready = [
            u
            for u in remaining
            if all((dep not in known_ids) or (dep in completed) for dep in u.get("depends_on", []))
        ]
        if not ready:
            # Break dependency cycle conservatively by running remaining units one by one
            ready = [remaining[0]]
        waves.append(ready)
        ready_ids = {u["id"] for u in ready}
        completed |= ready_ids
        remaining = [u for u in remaining if u["id"] not in ready_ids]
    return waves


def build_unit_agent(unit, run_in_share):
    skills_list = ", ".join(f"skills/{s}/SKILL.md" for s in unit["skills"])
    files_list = ", ".join(unit["files"])
    isolation_note = (
        "You are running in an isolated shared workspace; commit your unit changes cleanly in your branch and report changed files and test output."
        if run_in_share
        else "Edit only your owned files in place and verify tests pass."
    )
    return agent(
        prompt=(
            f"Implement AI-DLC Unit {unit['id']}: {unit['title']}\n\n"
            f"Business Rules (BR-*):\n{business_rules_block}\n\n"
            f"Design Context:\n{plan['design_doc']}\n\n"
            f"Owned Files (do NOT edit outside these): {files_list}\n"
            f"Acceptance Criteria: {unit['acceptance_criteria']}\n"
            f"Read these skills first: skills/tdd-implementation/SKILL.md, {skills_list}\n\n"
            f"{isolation_note}"
        ),
        schema=DEV_RESULT_SCHEMA,
        role=f"Implement {unit['id']}: {unit['title']}",
        type_name="developer",
        workspace="share" if run_in_share else "inherit",
    )


dev_results = []
for wave_idx, wave_units in enumerate(_compute_unit_waves(plan["units"]), 1):
    overlap = _wave_has_file_overlap(wave_units)
    if overlap:
        log(f"Wave {wave_idx}: overlapping file ownership detected; falling back to sequential execution.")
    wave_share = parallel_units and len(wave_units) > 1 and not overlap
    if wave_share:
        wave_res = await parallel(wave_units, lambda u: build_unit_agent(u, True))
        merge_summary = await agent(
            prompt=(
                f"Integrate Wave {wave_idx} parallel share-workspace unit branches into the main workspace "
                f"at {workspace_root} before proceeding to the next wave or verification:\n"
                f"{wave_res}\n\n"
                "Merge each unit's committed branch cleanly, verify git status is clean with no conflict markers, "
                "and return a brief integration summary."
            ),
            schema={"type": "string"},
            role=f"Integrate Wave {wave_idx} Branches",
            type_name="orchestrator",
            workspace="inherit",
        )
        log(f"Wave {wave_idx} merged into main workspace: {merge_summary}")
    else:
        wave_res = await pipeline(wave_units, lambda u: build_unit_agent(u, False))
    dev_results.extend(wave_res)

for res in dev_results:
    log(f"Unit {res['unit_id']} implemented: {res['summary']} | Tests: {res['test_results']}")

phase("Construction — Verification & Security")


async def run_reviews(context_note):
    checks = [
        agent(
            prompt=(
                "Read skills/code-review/SKILL.md. Review all implementation changes against "
                f"Business Rules (BR-*), acceptance criteria, and design:\n{business_rules_block}\n\n"
                f"{plan['design_doc']}\n\n"
                f"Implementation reports:\n{dev_results}\n\n{context_note}\n"
                "Run the actual test suite and report exact findings and approved boolean."
            ),
            schema=REVIEW_RESULT_SCHEMA,
            role="AI-DLC Verifier",
            type_name="verifier",
            workspace="inherit",
        )
    ]
    if run_security:
        checks.append(
            agent(
                prompt=(
                    "Read skills/security-audit/SKILL.md. Audit the design and implementation "
                    f"for security risks and Business Rule policy gaps:\n{business_rules_block}\n\n"
                    f"{plan['design_doc']}\n\n"
                    f"Implementation reports:\n{dev_results}\n\n{context_note}"
                ),
                schema=REVIEW_RESULT_SCHEMA,
                role="AI-DLC Security Audit",
                type_name="security",
                workspace="inherit",
            )
        )
    return await parallel(checks, lambda a: a)


reviews = await run_reviews("Initial Construction verification round.")
round_num = 1
while any(not r["approved"] for r in reviews) and round_num <= max_review_rounds:
    combined_findings = [f for r in reviews if not r["approved"] for f in r["findings"]]
    log(f"Review round {round_num} requested changes ({len(combined_findings)} finding(s)).")
    fix_res = await agent(
        prompt=(
            "Resolve all blocking verification/security findings below using TDD "
            "(read skills/systematic-debugging/SKILL.md and skills/tdd-implementation/SKILL.md):\n"
            + "\n".join(f"- {item}" for item in combined_findings)
        ),
        schema=DEV_RESULT_SCHEMA,
        role=f"Fix Review Findings (Round {round_num})",
        type_name="developer",
        workspace="inherit",
    )
    dev_results.append(fix_res)
    reviews = await run_reviews(f"Re-verification after fix round {round_num}: {fix_res['summary']}")
    round_num += 1

all_approved = all(r["approved"] for r in reviews)
log(f"Verification complete | Approved={all_approved}")

phase("Operation — Release Readiness")
op_report = await agent(
    prompt=(
        "Read skills/release-operations/SKILL.md and skills/technical-documentation/SKILL.md. "
        f"Summarize final release readiness for intent:\n{intent}\n\n"
        f"Approved={all_approved}\nUnits={dev_results}\nReviews={reviews}\n"
        "Include changed files, verified test evidence, docs status, and rollback notes."
    ),
    schema={"type": "string"},
    role="AI-DLC Operator",
    type_name="operator",
    workspace="inherit",
)
log(op_report)
print(op_report)
