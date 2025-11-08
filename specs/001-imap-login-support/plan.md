# Implementation Plan: IMAP Login Support

**Branch**: `001-imap-login-support` | **Date**: 2025-11-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-imap-login-support/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Add IMAP authentication support to enable Gmail access using email/password credentials as an alternative to OAuth2, enabling desktop-client-like login experience. This provides foundation for potential GUI implementation and simplifies authentication workflow for users who prefer traditional credential-based login.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: imapclient>=3.0.0 (IMAP client - chosen for Pythonic API, Gmail-tested, production-ready), google-api-python-client (existing), anthropic (existing), keyring (existing)
**Storage**: System credential manager (keyring) for secure IMAP credential storage, sqlite3 (existing session state)
**Testing**: pytest (existing)
**Target Platform**: Cross-platform (macOS, Linux, Windows) - CLI application
**Project Type**: Single project (existing CLI tool extension)
**Performance Goals**: IMAP authentication <10s, email retrieval <30s for first batch, re-authentication with saved credentials <5s
**Constraints**: Single persistent connection (no pooling needed for CLI), secure credential storage (OS keyring), IMAP SSL/TLS required (port 993), graceful fallback between OAuth2 and IMAP methods
**Scale/Scope**: Single-user Gmail accounts, support for 100,000+ email mailboxes, IMAP folder navigation (INBOX, Sent, Archive, custom labels)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Feature supports incremental user value (Principle IV)**: Yes - P1 (IMAP authentication) provides standalone value, P2 (credential storage) builds on P1, P3 (email retrieval) completes integration with existing classification
- [x] **Test-first workflow planned with approval checkpoint (Principle I)**: Yes - Contract tests for IMAP connection, integration tests for auth flow, will seek approval after test execution before implementation
- [x] **Data privacy requirements identified (Principle II)**: Yes - IMAP credentials stored in OS keyring (encrypted), no raw credential logging, PII sanitization in logs, existing privacy controls maintained
- [x] **Observability/logging approach defined (Principle III)**: Yes - Structured logging for IMAP connection state, authentication failures with clear error messages, connection metrics tracking (connection time, retry attempts)
- [x] **Gmail API integration follows best practices (Principle VI)**: RESOLVED - IMAP-only approach using X-GM-LABELS extension for label operations; 40x faster than Gmail API, no OAuth needed, complete label CRUD support
- [x] **Python virtual environment and uv tooling will be used (Principle V)**: Yes - .finance venv with uv for dependency management
- [x] **Scope is clear and bounded (Principle VII G1-G3)**: Yes - Limited to IMAP authentication, credential storage, and email retrieval; excludes GUI, SMTP, non-Gmail servers, multi-account; ~200-300 LOC estimated
- [x] **Code anchors planned for complex/ambiguous areas (Principle VIII)**: Yes - AIDEV-NOTE for IMAP library choice rationale, AIDEV-NOTE for label operations via X-GM-LABELS

**GATE STATUS**: ✅ PASS - All clarifications resolved in Phase 0 research, design artifacts complete in Phase 1

## Project Structure

### Documentation (this feature)

```text
specs/001-imap-login-support/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/gmail_classifier/
├── auth/
│   ├── oauth.py         # Existing OAuth2 authentication
│   └── imap.py          # NEW: IMAP authentication module
├── storage/
│   ├── credentials.py   # NEW: Credential storage using keyring
│   └── session.py       # Existing session state
├── email/
│   ├── fetcher.py       # MODIFIED: Add IMAP email retrieval
│   └── classifier.py    # Existing classification logic (unchanged)
└── cli/
    └── main.py          # MODIFIED: Add IMAP login commands

tests/
├── contract/
│   └── test_imap_connection.py  # NEW: IMAP protocol contract tests
├── integration/
│   └── test_imap_auth_flow.py   # NEW: End-to-end IMAP auth tests
└── unit/
    ├── test_imap_credentials.py  # NEW: Credential storage unit tests
    └── test_imap_parser.py       # NEW: IMAP response parsing tests
```

**Structure Decision**: Single project structure maintained. IMAP support added as new auth module alongside existing OAuth2. Existing classification logic remains authentication-method agnostic. Estimated 3-4 new files, 2 file modifications.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitution principles satisfied with Phase 0 research resolving initial concerns.
