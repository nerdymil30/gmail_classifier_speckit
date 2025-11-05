# Engineering Standards

> Baseline rules for how we build and ship code. The agent-specific workflow lives in `AGENT_RUNBOOK.md`.  
> Task planning details live in `docs/memory_bank/guides/TASK_PLAN_GUIDE.md`.

## 0) Scope
Engineering rules only: repo layout, coding/testing/tooling, quality gates.

---

## 1) Repository Layout (Python baseline)
```
project_name/
├─ docs/
│  ├─ CHANGELOG.md
│  ├─ memory_bank/
│  └─ tasks/
├─ examples/                 # mirrors src/ for runnable snippets
├─ pyproject.toml            # managed by uv
├─ README.md
├─ src/project_name/
├─ tests/                    # mirrors src/
│  ├─ fixtures/
│  └─ project_name/
└─ uv.lock
```
**Rules**
- **Mirror Structure**: `tests/` and `examples/` mirror `src/`.
- **Package Manager**: Use `uv` with `pyproject.toml`. Don’t use `pip` directly.
- **Docs**: User-facing docs live under `docs/`. Each public module has a short example/README.

---

## 2) Coding Guidelines
- **Function-first**. Classes for:
  - Stateful components
  - Domain/data models
  - Established patterns (e.g., Strategy, Adapter)
- **Async**: Never call `asyncio.run()` inside library code; only at app/CLI entrypoints.
- **Type hints**: Required for all public functions & returns. Enforce with mypy (or pyright). Avoid `Any` unless unavoidable.
- **Module size**: Keep modules small (≈≤500 LOC guideline). Split before they bloat.
- **Imports**
  - **Required deps**: import at top. **No try/except** around required imports.
  - **Optional features**: expose via `extras` in `pyproject.toml` and **lazy import** at feature boundary with a clear error.
- **Logging**
  - Apps/CLIs: `loguru` (or stdlib `logging`) acceptable.
  - Libraries: keep logging minimal and non-intrusive.
- **CLI**: Prefer `typer` for CLI apps; libraries shouldn’t depend on it unless they ship a CLI.

---

## 3) Testing & Quality Gates
- **Test layers**
  1) **Unit** (fast, deterministic) with fixtures/fakes.
  2) **Integration** (real subsystems; minimize external calls).
  3) **E2E/Smoke** (real data if needed).
- **Mocks**: Allowed at external boundaries (network/filesystem/process). Avoid mocking internal code; prefer fakes/fixtures.
- **Real data**: Use only where it proves real behavior (integration/E2E), not for unit tests.
- **Framework**: `pytest` + `pytest-cov`.
- **CI gates (must pass)**
  - `ruff format` + `ruff check` (or equivalent)
  - `mypy` (or pyright) for public APIs
  - `pytest -q` (no flakiness)

---

## 4) Development Order of Operations
1) Make it work (small vertical slice).
2) Cover with tests (unit first; integration if relevant).
3) Refactor for clarity.
4) Lint/typecheck and docs polish.

> We don’t block on lint before green tests, but formatting runs on every commit.

---

## 5) Execution Standards
- Run scripts: `uv run script.py`
- Env vars: `env VAR=value uv run command`
- Provide repeatable targets (choose one): `Makefile` or `justfile`.

---

## 6) Optional Dependencies (pattern)
```python
def _has_pandas() -> bool:
    try:
        import pandas as _pd  # noqa
        return True
    except Exception:
        return False

def to_dataframe(rows):
    if not _has_pandas():
        raise RuntimeError("Install with extras: `pip install .[pandas]`")
    import pandas as pd
    return pd.DataFrame(rows)
```

**Typer CLI skeleton**
```python
import typer
app = typer.Typer()

@app.command()
def run(input_path: str):
    """Run the pipeline on input_path."""
    ...

if __name__ == "__main__":
    app()
```

---

## 7) Engineering Compliance Checklist (tick before merge)
- [ ] Module ≈≤500 LOC or split planned.
- [ ] Public APIs fully type-hinted; mypy/pyright clean.
- [ ] No `asyncio.run()` in library code.
- [ ] Required deps imported at top; optional deps via extras + lazy import.
- [ ] Tests added/updated; `pytest -q` passes; coverage hits changed paths.
- [ ] Mocks only at external boundaries; fixtures/fakes elsewhere.
- [ ] `ruff format` / `ruff check` clean.
- [ ] Examples/README updated if behavior changed.
- [ ] CI green on all gates.
