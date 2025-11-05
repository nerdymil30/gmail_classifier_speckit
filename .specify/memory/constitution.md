<!--
  Sync Impact Report
  ==================
  Version change: 1.1.0 → 1.1.1
  Modified principles:
    - Principle I: Clarified test approval workflow - agents write spec/unit tests then seek
      explicit approval after execution, rather than before writing
  Added sections: None
  Removed sections: None

  Templates requiring updates:
  ✅ plan-template.md - Constitution Check section references this file
  ✅ spec-template.md - User scenarios align with principle focus
  ✅ tasks-template.md - Task structure supports test-first principles
  ⚠ May need to update any automation scripts to use uv commands

  Follow-up TODOs: None
-->

# Gmail Classifier Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)

Tests MUST be written before implementation begins. The workflow is:
1. **Agent writes test cases** based on specifications (spec tests and unit tests)
2. **Agent executes tests** to verify they fail (red phase)
3. **Agent seeks explicit user approval** of the test design and results
4. After approval: Implement feature to pass tests (green phase)
5. Refactor as needed

**Agent test ownership and approval workflow**:
- **Spec tests** (contract/integration): Agent MAY write these tests proactively but MUST
  obtain explicit user approval after writing and executing them, before proceeding to
  implementation. These tests define system contracts and user journeys.
- **Unit tests**: Agent MAY write and modify unit tests in `tests/unit/` alongside code
  changes without explicit approval. These test internal implementation details.

**Approval checkpoint**: After writing spec tests (contract/integration), agent MUST:
1. Present the test code and test results (failing tests)
2. Explain what each test validates and why
3. Wait for explicit user approval before implementing features

**Rationale**: Gmail classification errors can lead to lost emails, privacy breaches, or
workflow disruptions. Test-first ensures correctness before deployment. Spec tests require
approval because they define system contracts and user expectations. Unit tests can be
modified freely as implementation details evolve.

### II. Data Privacy & Security

All email data handling MUST:
- Never persist raw email content unless explicitly required and approved
- Sanitize PII (personally identifiable information) from logs
- Use secure credential storage for Gmail API access
- Implement rate limiting to respect Gmail API quotas
- Support local-only processing modes

**Rationale**: Email contains sensitive personal and business information. Security
breaches or privacy violations can have severe legal and reputational consequences.

### III. Observability & Debugging

All classification operations MUST be observable:
- Structured logging for classification decisions (what, why, confidence score)
- Input/output validation with clear error messages
- Classification metrics tracking (accuracy, false positives, processing time)
- Dry-run mode for testing classification rules without applying changes

**Rationale**: ML classification models are inherently probabilistic. Users need
transparency into why emails were classified certain ways and ability to debug
misclassifications without risk.

### IV. Incremental User Value

Features MUST be delivered as independently testable user stories:
- Each story provides standalone value (e.g., "classify emails by sender")
- Stories can be deployed incrementally without breaking existing functionality
- MVP (Minimum Viable Product) delivers core classification before advanced features
- Prioritize P1 (critical) stories before P2/P3 enhancements

**Rationale**: Users need working classification quickly. Incremental delivery allows
early feedback and course correction, preventing wasted effort on unwanted features.

### V. Python Virtual Environment & Tooling Discipline

ALL Python code execution MUST use the `.finance` virtual environment with `uv` tooling:
- Activate environment: `source /Users/ravivedula/Library/CloudStorage/Dropbox/1-projects/Coding/.finance/bin/activate`
- Use `uv` for dependency management: `uv sync --all-extras --dev`
- Install packages ONLY after user approval
- Document all dependencies in `pyproject.toml` or `requirements.txt`
- Never install packages globally or in other environments
- Use configured tools: `uv`, `pytest`, `ruff`, `mypy`

**Rationale**: Environment isolation prevents dependency conflicts, ensures reproducible
builds, and maintains consistency across development and production. Modern tooling (`uv`)
provides faster, more reliable dependency resolution.

### VI. API Integration Best Practices

Gmail API integration MUST follow:
- Respect API rate limits (batch operations when possible)
- Implement exponential backoff for transient errors
- Handle API quota exhaustion gracefully (user notification)
- Support offline development modes (mock responses for testing)
- Version compatibility checks for Gmail API changes

**Rationale**: Gmail API has strict quotas and error handling requirements. Proper
integration prevents service disruptions and improves user experience during failures.

### VII. Scope Discipline (Golden Rules)

**G1 – Ask when unsure**: If a requirement or file target is ambiguous, MUST pause and
ask the maintainer before proceeding.

**G2 – Stay in scope**: MUST only touch files relevant to the current task. No scope
creep without explicit approval.

**G3 – Big changes need approval**: If a change exceeds 300 LOC or affects 3+ files,
MUST post a plan and wait for approval before implementation.

**G4 – Respect generated code**: MUST NOT edit generated artifacts directly. Update the
source specification and regenerate. (Only applies where codegen exists.)

**Rationale**: Scope discipline prevents unintended side effects, maintains code review
quality, and ensures changes align with user expectations. Large changes without review
risk introducing bugs or misaligned features.

### VIII. Code Anchors & Documentation

Use grep-able anchors in code for AI and human context:
- `AIDEV-NOTE:` short context or performance caveats
- `AIDEV-TODO:` follow-ups suitable for a task card
- `AIDEV-QUESTION:` uncertainty requiring maintainer answer

**Rules**:
- Keep anchors ≤120 characters
- MUST update or remove anchors when code changes
- Place near relevant code, not in distant comments

**Rationale**: Anchors create searchable documentation that helps both humans and AI
agents understand context, track technical debt, and identify areas needing clarification
without relying on external documentation.

## Tooling Standards

### Required Commands (Single Source of Truth)

```bash
# Dependency management
uv sync --all-extras --dev

# Code formatting
uv run ruff format .

# Linting
uv run ruff check .

# Type checking
uv run mypy src

# Test execution
uv run pytest -q
```

### Makefile/Justfile Integration

If `Makefile` or `justfile` exists in the project, MUST use defined targets instead of
direct commands. Check for targets before running raw tool commands.

### Don'ts

- DON'T refactor broadly without approval (see Principle VII G3)
- DON'T invent new toolchains (stick to configured: uv, pytest, ruff, mypy)
- DON'T claim success unless tests actually pass
- DON'T skip type checking or linting before committing

## Testing Requirements

### Mandatory Test Categories

1. **Contract Tests**: Verify Gmail API integration contracts
   - Mock API responses for common scenarios
   - Test authentication flow
   - Validate request/response schemas
   - **Ownership**: Agent writes, MUST get approval after execution

2. **Classification Logic Tests**: Core algorithm correctness
   - Known email samples with expected classifications
   - Edge cases (empty emails, malformed headers, special characters)
   - Confidence threshold validation
   - **Ownership**: Agent writes, MUST get approval after execution

3. **Integration Tests**: End-to-end user journeys
   - Complete classification workflow (fetch → classify → apply)
   - Error recovery scenarios
   - Multi-label classification handling
   - **Ownership**: Agent writes, MUST get approval after execution

4. **Unit Tests**: Component implementation details
   - Utility functions
   - Data transformation logic
   - Configuration parsing
   - **Ownership**: Agent MAY write/modify without explicit approval

### Test Organization

```
tests/
├── contract/          # API contract tests (requires user approval after execution)
├── integration/       # End-to-end tests (requires user approval after execution)
└── unit/             # Component tests (agent may modify freely)
```

### Test Approval Process

**For spec tests (contract/integration)**:
1. Agent writes test cases based on specifications
2. Agent executes tests (should fail initially - red phase)
3. Agent presents to user:
   - Test code with explanations
   - Test execution results
   - What each test validates and why it matters
4. **CHECKPOINT**: User reviews and approves OR requests changes
5. After approval: Agent implements features to pass tests

**For unit tests**:
1. Agent writes alongside code changes
2. No explicit approval required
3. Must pass before commit

## Development Workflow

### Feature Implementation

1. **Specification**: Create spec.md with user stories (prioritized P1, P2, P3)
2. **Planning**: Generate plan.md with technical approach and constitution check
3. **Test Design**: Write spec tests (contract/integration) for P1 story
4. **Test Execution**: Run tests to verify they fail (red phase)
5. **Approval Checkpoint**: Present tests to user and obtain explicit approval
6. **Implementation**: Implement P1 story to pass tests (green phase)
7. **Validation**: Run full test suite, verify P1 story works independently
8. **Quality Gates**: Run ruff format, ruff check, mypy, pytest before committing
9. **Iterate**: Repeat for P2, P3... or stop at MVP if sufficient

### Constitution Check (Pre-Implementation Gate)

Before Phase 0 research, verify:
- [ ] Feature supports incremental user value (Principle IV)
- [ ] Test-first workflow planned with approval checkpoint (Principle I)
- [ ] Data privacy requirements identified (Principle II)
- [ ] Observability/logging approach defined (Principle III)
- [ ] Gmail API integration follows best practices (Principle VI)
- [ ] Python virtual environment and uv tooling will be used (Principle V)
- [ ] Scope is clear and bounded (Principle VII G1-G3)
- [ ] Code anchors planned for complex/ambiguous areas (Principle VIII)

### Complexity Justification

Any deviation from principles MUST be documented in plan.md complexity tracking:
- Why the deviation is necessary
- What simpler alternative was rejected and why
- Mitigation plan to return to compliance

### Where to Look First

When starting work or uncertain about conventions:
1. Engineering rules → `ENGINEERING_STANDARDS.md` (if present)
2. Agent workflow → `AGENT_RUNBOOK.md` (if present)
3. Task format → `docs/memory_bank/guides/TASK_PLAN_GUIDE.md` (if present)
4. Directory-specific rules → Local `AGENTS.md` files where present
5. This constitution → `.specify/memory/constitution.md`

## Governance

### Amendment Process

1. Identify principle addition/change needed
2. Document rationale and impact on existing features
3. Update constitution version (semantic versioning)
4. Propagate changes to plan-template.md, spec-template.md, tasks-template.md
5. Commit with message: `docs: amend constitution to vX.Y.Z (description)`

### Version Semantics

- **MAJOR**: Breaking governance change (principle removal/incompatible redefinition)
- **MINOR**: New principle added or materially expanded guidance
- **PATCH**: Clarifications, wording improvements, non-semantic refinements

### Compliance Reviews

- All PRs MUST verify compliance with constitution principles
- Complexity violations require explicit justification in plan.md
- User approval required for any principle deviations
- Quality gates (ruff, mypy, pytest) MUST pass before merge

### Runtime Guidance

For implementation-time decisions not covered by constitution, refer to:
- Python virtual environment rules in CLAUDE.md
- Gmail API documentation and best practices
- User preferences and project-specific constraints
- ENGINEERING_STANDARDS.md and AGENT_RUNBOOK.md (if present)

**Version**: 1.1.1 | **Ratified**: 2025-11-05 | **Last Amended**: 2025-11-05
