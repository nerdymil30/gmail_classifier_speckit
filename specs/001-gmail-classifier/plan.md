# Implementation Plan: Gmail Classifier & Organizer

**Branch**: `001-gmail-classifier` | **Date**: 2025-11-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-gmail-classifier/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a Gmail classification system that analyzes unlabeled emails and suggests appropriate labels based on user's existing organizational framework. The system generates summary briefs for emails that don't match existing patterns and provides a review interface for bulk approval of classification suggestions. **Critical constraint**: Read-only mode with NO deletion capability.

**Technical Approach**: Python-based CLI/library using Gmail API for email access, Claude SDK (Haiku model) for AI-powered classification and summarization, and structured logging for transparency. Batch processing (10 emails at a time) with OAuth2 authentication, user consent for cloud processing, and exponential backoff for API rate limiting.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: google-api-python-client (Gmail API), anthropic (Claude SDK for classification), google-auth-oauthlib (OAuth2), keyring (credential storage), sqlite3 (session state)
**Storage**: Local SQLite for session state and processing logs; NO persistent storage of email content (privacy requirement)
**Testing**: pytest with mock Gmail API and Claude API responses
**Target Platform**: Local development machine (macOS/Linux/Windows) with Python environment
**Project Type**: single (CLI application with library core)
**Performance Goals**: Process minimum 20 emails/minute; classify 100 emails in under 5 minutes including review time
**Constraints**: Read-only Gmail API permissions; no email deletion; English-only classification; Gmail API quota limits (250 units/user/second); Claude API rate limits; user consent required for cloud processing
**Scale/Scope**: Support 250-500 emails per classification session; handle up to 1000 unlabeled emails in single account; batch processing in groups of 10 emails

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I - Test-First Development**: Plan includes contract tests for Gmail API, integration tests for classification workflow, and unit tests for utilities. Test approval checkpoint documented.
- [x] **Principle II - Data Privacy & Security**: OAuth2 with read-only scope; no raw email persistence (only IDs and metadata); PII sanitization in logs; local-only processing mode.
- [x] **Principle III - Observability**: Structured logging for classification decisions with confidence scores; dry-run mode supported; processing log tracks all operations.
- [x] **Principle IV - Incremental User Value**: P1 (classify emails) provides standalone MVP value; P2 (summaries) and P3 (review interface) are independent enhancements.
- [x] **Principle V - Python Virtual Environment**: Will use `.finance` virtual environment with `uv` tooling; dependencies in `pyproject.toml`.
- [x] **Principle VI - API Integration Best Practices**: Exponential backoff for Gmail API; quota monitoring; offline mock mode for testing; batch operations where possible.
- [x] **Principle VII - Scope Discipline**: Feature clearly bounded as read-only classifier; no scope creep into email management or deletion.
- [x] **Principle VIII - Code Anchors**: Will use AIDEV-NOTE/TODO/QUESTION anchors for ML model choices, API quota handling, and classification algorithm tuning.

**Gate Result**: ✅ PASS - No constitution violations. All principles addressed in planning phase.

## Project Structure

### Documentation (this feature)

```text
specs/001-gmail-classifier/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── gmail-api-contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── gmail_classifier/
│   ├── __init__.py
│   ├── auth/                 # OAuth2 authentication
│   │   ├── __init__.py
│   │   └── gmail_auth.py
│   ├── models/               # Data models
│   │   ├── __init__.py
│   │   ├── email.py          # Email entity
│   │   ├── label.py          # Label entity
│   │   ├── suggestion.py     # Classification suggestion
│   │   └── session.py        # Processing session
│   ├── services/             # Core business logic
│   │   ├── __init__.py
│   │   ├── gmail_client.py   # Gmail API wrapper
│   │   ├── claude_client.py  # Claude API wrapper (Haiku)
│   │   ├── classifier.py     # Classification engine (uses Claude)
│   │   ├── summarizer.py     # Brief generation (uses Claude)
│   │   └── reviewer.py       # Review/approval workflow
│   ├── cli/                  # CLI interface
│   │   ├── __init__.py
│   │   └── main.py
│   └── lib/                  # Shared utilities
│       ├── __init__.py
│       ├── logger.py         # Structured logging
│       └── config.py         # Configuration management

tests/
├── contract/                 # Gmail API contract tests
│   ├── __init__.py
│   └── test_gmail_api.py
├── integration/              # End-to-end tests
│   ├── __init__.py
│   ├── test_classify_workflow.py
│   └── test_summary_workflow.py
└── unit/                     # Component tests
    ├── __init__.py
    ├── test_classifier.py
    ├── test_summarizer.py
    └── test_gmail_client.py

pyproject.toml                # uv dependency management
README.md                     # User-facing documentation
.env.example                  # OAuth credentials template
```

**Structure Decision**: Single project structure selected because this is a CLI application with library core. No frontend/backend split needed; no mobile components. All code in `src/gmail_classifier/` with clear separation: auth (OAuth2), models (entities), services (business logic), cli (interface), lib (utilities).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No complexity violations - all constitution principles satisfied.*

---

## Phase 0: Research & Technology Decisions

**Status**: ✅ COMPLETE - All technology choices made

### Research Decisions

1. **Gmail API Client Library**: ✅ **google-api-python-client** (official)
   - Rationale: Official library with modern OAuth2 support, production-ready, full Gmail API coverage, active maintenance
   - Best practices: Exponential backoff for rate limits, batch operations, mock responses for testing

2. **Classification & Summarization**: ✅ **anthropic SDK** with Claude Haiku model
   - Rationale: High-quality semantic understanding via Claude API, no local ML model needed, consistent AI approach for both classification and summarization, handles label constraint enforcement naturally
   - Performance: Cloud-based API calls, ~200-500ms per request, batch processing (10 emails at a time)
   - Privacy: Requires user consent for sending full email content to Anthropic API

3. **OAuth2 & Credential Storage**: ✅ **keyring library** (system keyring)
   - Rationale: Cross-platform secure credential storage, OS-level encryption, easy re-authentication flow
   - Implementation: Store refresh token (Gmail) and API key (Claude) securely

4. **Session State Management**: ✅ **SQLite** (structured)
   - Rationale: Structured queries for reporting, ACID compliance for resume capability, human-readable with SQL tools
   - Schema: ProcessingSession, ClassificationSuggestion tables with foreign keys

### Research Output

Comprehensive findings documented in: `specs/001-gmail-classifier/research.md`

---

## Phase 1: Design Artifacts

**Status**: ✅ COMPLETE - All design artifacts generated

### Generated Artifacts

1. ✅ **data-model.md** - Complete entity definitions
   - Email entity (15 fields including Gmail API properties)
   - Label entity (5 fields with embedding vector for classification)
   - ClassificationSuggestion (nested SuggestedLabel type with confidence/rank)
   - SummaryBrief (grouping by sender/topic/domain with suggested actions)
   - ProcessingSession (resume capability with state tracking)
   - Entity relationships diagram and privacy constraints documented

2. ✅ **contracts/gmail-api-contract.md** - Gmail API integration contracts
   - OAuth2 authentication flow with keyring storage
   - 4 primary endpoints: list labels, list messages, get message, modify labels
   - Rate limiting strategy (250 units/sec quota management)
   - Exponential backoff implementation with jitter
   - Error handling matrix for all HTTP codes
   - Mock responses for contract testing

3. ✅ **quickstart.md** - Getting started guide (10-minute setup)
   - Step-by-step: Environment setup, Gmail API credentials, authentication
   - Dry-run classification walkthrough with example output
   - Summary brief generation examples
   - Interactive review mode usage
   - Common commands reference and troubleshooting
   - Security notes and safety features

### Design Output Files

- `specs/001-gmail-classifier/data-model.md` (created)
- `specs/001-gmail-classifier/contracts/gmail-api-contract.md` (created)
- `specs/001-gmail-classifier/quickstart.md` (created)
- `CLAUDE.md` (updated with technology stack)

---

## Next Steps After Planning

1. **Run `/speckit.tasks`** to generate task breakdown for implementation
2. **Implement P1** (classify unlabeled emails) as MVP
3. **Test P1** independently before proceeding to P2
4. **Iterate** through P2 (summaries) and P3 (review) as enhancements
