# AGENTS.md (Overlay)

**Purpose** — This page is the quick-start for humans and AI assistants.  
**Canonical rules live in:** `ENGINEERING_STANDARDS.md` and `AGENT_RUNBOOK.md`.

## 1) Golden Rules (non-negotiable)
- **G1 – Ask when unsure:** If a requirement or file target is ambiguous, pause and ask the maintainer.
- **G2 – Stay in scope:** Only touch files relevant to the current task/card.
- **G3 – Big changes need a nod:** If a change exceeds **300 LOC or 3 files**, post a plan and wait for approval.
- **G4 – Respect generated code:** Do not edit generated artifacts; update the source (spec) and regenerate. *(Only applies where codegen exists.)*
- **G5 – Follow the configured tools:** Use `uv`, `pytest`, `ruff`, `mypy` and the `Makefile/justfile` targets if present.

> **Tests policy:** Agents **may** add/modify **unit tests** in `tests/` alongside changed code. Humans own **acceptance/spec** tests.

## 2) Anchors for AI/Humans
Use grep-able anchors in critical or tricky spots:
- `AIDEV-NOTE:` short context or performance caveats
- `AIDEV-TODO:` follow-ups suitable for a task card
- `AIDEV-QUESTION:` uncertainty that needs a maintainer answer

Keep anchors ≤120 chars. Update/remove them when the code changes.

## 3) Where to look first
- Engineering rules → `ENGINEERING_STANDARDS.md`
- Agent workflow → `AGENT_RUNBOOK.md`
- Task format/acceptance → `docs/memory_bank/guides/TASK_PLAN_GUIDE.md`
- Directory-specific rules → see local `AGENTS.md` files where present

## 4) Commands (single source of truth)
```bash
uv sync --all-extras --dev
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest -q
```

## 5) Don’ts
- Don’t refactor broadly without approval (see G3).
- Don’t invent toolchains (stick to the configured ones).
- Don’t claim success unless tests actually pass.
