# Agent Runbook

> How agents read tasks, implement, validate, and report. Engineering rules live in `ENGINEERING_STANDARDS.md`.  
> Task card format and acceptance criteria: `docs/memory_bank/guides/TASK_PLAN_GUIDE.md`.

## 0) Scope
This is the operational workflow for agents. Keep it short, follow it exactly.

---

## 1) Before You Start
- Read the task card and acceptance criteria.
- Identify entrypoints and impacted modules.
- Confirm optional dependencies/extras if the task uses them.

---

## 2) Build (smallest vertical slice)
- Implement the minimal path that satisfies acceptance criteria.
- Update or add **unit tests** alongside the code.
- Add **integration tests** if you touched I/O, network, or cross-service boundaries.
- Add/adjust example in `examples/` if it helps human validation.

---

## 3) Validate
- Run `pytest -q`; fix failures.
- If the same failure persists after **3 distinct attempts**, perform **external research** using an approved web-research tool (vendor-neutral).  
  Add a short comment in the code or PR description:
  - Link, 1-line takeaway, version/date sensitivity if any.

**Do NOT** claim success unless tests actually pass.

---

## 4) Report (when you open the PR)
Provide a tight summary:
- **What changed** (1–3 bullets)
- **How validated** (tests/commands)
- **Known limitations** / follow-ups
- **Optional deps** (extras) if used and how they’re guarded

Example:
```
Changes: add CSV loader, streaming parser
Validation: pytest -q (22 passed), local CSVs in examples/ ingest in 1.2s
Limits: large quoted fields cause backtracking; tracked in #123
Extras: pandas path guarded; `pip install .[pandas]`
```

---

## 5) Validation Output Requirements (strict)
- Never print “All tests passed” unless **all tests** actually passed.
- Always verify actual vs expected results before any success message.
- Include multiple cases (normal, edge, error-handling) in tests.
- Track **all** failures and report counts (e.g., “3 of 12 tests failed”).
- Exit code **1** if any tests fail; **0** only if all pass.
- Don’t drown failures in noise: keep output focused.

---

## 6) Agent Compliance Checklist (tick before handing off)
- [ ] Smallest vertical slice implemented.
- [ ] Unit tests added/updated and passing.
- [ ] Integration/E2E added if touching I/O or external systems.
- [ ] External research performed after 3 failed attempts, with note.
- [ ] No fake “success” messages; outputs reflect real test results.
- [ ] Optional deps handled via extras + lazy import.
- [ ] Report includes changes, validation, limits, extras.
- [ ] Links to updated examples/docs where relevant.

---

## 7) Quick Commands
```bash
# Install dev deps (via uv)
uv sync --all-extras --dev

# Format, lint, typecheck, test
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest -q

# Run example / CLI
uv run python examples/smoke.py
uv run python -m project_name.cli run ./data/input.csv
```
