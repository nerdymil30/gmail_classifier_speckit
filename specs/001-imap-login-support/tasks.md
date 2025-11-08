# Implementation Tasks: IMAP Login Support

**Feature**: 001-imap-login-support
**Generated**: 2025-11-07
**Status**: Ready for implementation

---

## Overview

This document provides actionable, dependency-ordered tasks for implementing IMAP authentication support in the Gmail classifier. Tasks are organized by user story to enable incremental, independently testable implementation.

**Total Tasks**: 39
**User Stories**: 3 (P1: IMAP Authentication, P2: Credential Storage, P3: Email Retrieval)
**Estimated LOC**: ~250-300 lines

---

## Implementation Strategy

### MVP Scope (Recommended First Iteration)
- **User Story 1 (P1)**: IMAP Credential Login
  - Delivers immediate value: Alternative authentication without OAuth2
  - Independently testable: Can authenticate and verify connection
  - Completion criteria: User can login with IMAP credentials and see connection success

### Incremental Delivery
1. **MVP**: Complete User Story 1 (P1) only - ~40% of total effort
2. **Enhanced UX**: Add User Story 2 (P2) - credential persistence
3. **Full Integration**: Add User Story 3 (P3) - email retrieval with classification

---

## Dependencies

### Story Completion Order

```
Setup (Phase 1) → Foundational (Phase 2) → User Story 1 (P1) → User Story 2 (P2) → User Story 3 (P3) → Polish
                                               ↓ (can start after)    ↓ (can start after)    ↓
                                          User Story 2 (P2)      User Story 3 (P3)        Polish
```

**Story Independence**:
- ✅ **User Story 1 (P1)**: No dependencies (can start after Foundational)
- ⚠️  **User Story 2 (P2)**: Requires User Story 1 (builds on authentication)
- ⚠️  **User Story 3 (P3)**: Requires User Story 1 (uses IMAP session)

**Parallel Opportunities**:
- **Within User Story 1**: Tests + Models can run in parallel
- **Within User Story 2**: Tests + Storage implementation can run in parallel
- **Within User Story 3**: Tests + Folder operations can run in parallel

---

## Phase 1: Setup

**Goal**: Prepare project infrastructure for IMAP support implementation

**Tasks** (4 tasks):

- [X] T001 Install imapclient dependency (requires user approval per CLAUDE.md): `pip install imapclient>=3.0.0`
- [X] T002 [P] Create auth module directory: `src/gmail_classifier/auth/__init__.py`
- [X] T003 [P] Create storage module directory: `src/gmail_classifier/storage/__init__.py`
- [X] T004 [P] Update pyproject.toml to add imapclient>=3.0.0 to dependencies array

**Completion Criteria**:
- ✅ imapclient library installed and importable
- ✅ Module directories exist
- ✅ pyproject.toml updated

---

## Phase 2: Foundational

**Goal**: Implement shared infrastructure needed by all user stories

**Tasks** (5 tasks):

- [X] T005 [P] Create SessionState enum in `src/gmail_classifier/auth/imap.py` with states: CONNECTING, CONNECTED, DISCONNECTED, ERROR
- [X] T006 [P] Create custom exception classes in `src/gmail_classifier/auth/imap.py`: AuthenticationError, ConnectionError, SessionError
- [X] T007 [P] Create IMAPCredentials dataclass in `src/gmail_classifier/auth/imap.py` with fields: email, password, created_at, last_used
- [X] T008 [P] Create IMAPSessionInfo dataclass in `src/gmail_classifier/auth/imap.py` with fields: session_id, email, selected_folder, connected_at, last_activity, state, retry_count
- [X] T009 Create logging configuration for IMAP operations in `src/gmail_classifier/auth/imap.py` with structured logging for connection events

**Completion Criteria**:
- ✅ All data structures defined and typed
- ✅ Exception hierarchy established
- ✅ Logging configured for observability

---

## Phase 3: User Story 1 - IMAP Credential Login (P1)

**Story Goal**: Enable users to authenticate to Gmail using IMAP credentials (email + app password) instead of OAuth2

**Independent Test**: User provides valid IMAP credentials → System authenticates successfully → Connection established to Gmail IMAP server → User sees success confirmation

**Acceptance Criteria**:
1. Valid IMAP credentials → Successful authentication and connection
2. Invalid credentials → Clear error message displayed
3. IMAP disabled account → Helpful guidance on enabling IMAP

**Tasks** (12 tasks):

### Tests (TDD - Write First, Seek Approval)

- [X] T010 [P] [US1] Write contract test for IMAP connection in `tests/contract/test_imap_connection.py` - Test basic connection to imap.gmail.com:993 with SSL
- [X] T011 [P] [US1] Write contract test for authentication in `tests/contract/test_imap_connection.py` - Test successful login with valid credentials
- [X] T012 [P] [US1] Write contract test for auth failures in `tests/contract/test_imap_connection.py` - Test invalid credentials, network errors, timeout scenarios
- [X] T013 [P] [US1] Write integration test for complete auth flow in `tests/integration/test_imap_auth_flow.py` - Test end-to-end: credentials → authenticate → verify connection

**Approval Checkpoint**: Present tests T010-T013 to user, explain what each validates, run tests (should FAIL), obtain explicit approval before proceeding

### Implementation

- [X] T014 [US1] Implement IMAPAuthenticator class skeleton in `src/gmail_classifier/auth/imap.py` with __init__, _sessions dict, _logger
- [X] T015 [US1] Implement authenticate() method in `src/gmail_classifier/auth/imap.py` with basic connection logic: IMAPClient('imap.gmail.com', ssl=True), login(), create IMAPSessionInfo
- [X] T016 [US1] Add retry logic with exponential backoff to authenticate() in `src/gmail_classifier/auth/imap.py` - Max 5 attempts, initial delay 3s, exponential backoff 2^retry_count
- [X] T017 [US1] Implement disconnect() method in `src/gmail_classifier/auth/imap.py` - Call IMAPClient.logout(), remove session from _sessions dict, log disconnect event
- [X] T018 [US1] Implement is_alive() method in `src/gmail_classifier/auth/imap.py` - Check if session exists and connection responds to NOOP
- [X] T019 [US1] Add error handling for common failures in `src/gmail_classifier/auth/imap.py` - Catch IMAP exceptions, translate to custom exceptions (AuthenticationError, ConnectionError)
- [X] T020 [US1] Add credential validation in `src/gmail_classifier/auth/imap.py` - Validate email format (regex), password length (8-64 chars), sanitize from error messages
- [X] T021 [US1] Run tests T010-T013 and verify all pass - Ensure 100% pass rate before proceeding

**Completion Criteria**:
- ✅ All contract tests pass (T010-T012)
- ✅ Integration test passes (T013)
- ✅ User can authenticate with valid credentials in <10s
- ✅ Invalid credentials show clear error messages
- ✅ Connection errors handled with retry logic

---

## Phase 4: User Story 2 - Secure Credential Storage (P2)

**Story Goal**: Allow users to save IMAP credentials securely so they don't have to re-enter them on each application start

**Independent Test**: User logs in with IMAP → Chooses to save credentials → Closes application → Reopens application → Automatically authenticated without re-entering credentials

**Acceptance Criteria**:
1. User logs in → Prompt to save credentials → Stored in OS keyring
2. Saved credentials exist → Auto-authenticate on app start
3. User logs out → Old credentials removed, optionally store new ones

**Tasks** (11 tasks):

### Tests (TDD - Write First, Seek Approval)

- [X] T022 [P] [US2] Write unit test for credential storage in `tests/unit/test_imap_credentials.py` - Test store_credentials() saves to keyring
- [X] T023 [P] [US2] Write unit test for credential retrieval in `tests/unit/test_imap_credentials.py` - Test retrieve_credentials() loads from keyring
- [X] T024 [P] [US2] Write unit test for credential deletion in `tests/unit/test_imap_credentials.py` - Test delete_credentials() removes from keyring
- [X] T025 [P] [US2] Write integration test for auto-auth flow in `tests/integration/test_imap_auth_flow.py` - Test saved credentials → auto-authenticate → success

**Approval Checkpoint**: Present tests T022-T025 to user, explain what each validates, run tests (should FAIL), obtain explicit approval before proceeding

### Implementation

- [X] T026 [US2] Create CredentialStorage class in `src/gmail_classifier/storage/credentials.py` with __init__, _service_name="gmail_classifier_imap"
- [X] T027 [P] [US2] Implement store_credentials() method in `src/gmail_classifier/storage/credentials.py` - Use keyring.set_password(service_name, email, password), set created_at timestamp
- [X] T028 [P] [US2] Implement retrieve_credentials() method in `src/gmail_classifier/storage/credentials.py` - Use keyring.get_password(service_name, email), return IMAPCredentials dataclass
- [X] T029 [P] [US2] Implement delete_credentials() method in `src/gmail_classifier/storage/credentials.py` - Use keyring.delete_password(service_name, email), return success boolean
- [X] T030 [P] [US2] Implement has_credentials() method in `src/gmail_classifier/storage/credentials.py` - Check if credentials exist for email without retrieving password
- [X] T031 [US2] Add update_last_used() method in `src/gmail_classifier/storage/credentials.py` - Update timestamp on successful authentication (requires storing metadata separately from keyring)
- [X] T032 [US2] Run tests T022-T025 and verify all pass - Ensure 100% pass rate before proceeding

**Completion Criteria**:
- ✅ All unit tests pass (T022-T024)
- ✅ Integration test passes (T025)
- ✅ Credentials stored securely in OS keyring (not plain text)
- ✅ Auto-authentication works in <5s on subsequent starts
- ✅ Logout clears stored credentials

---

## Phase 5: User Story 3 - Email Retrieval via IMAP (P3)

**Story Goal**: Enable users to retrieve and classify emails from Gmail using IMAP connection after authentication

**Independent Test**: User authenticates via IMAP → Requests to fetch emails → System retrieves emails from INBOX → Emails available for classification

**Acceptance Criteria**:
1. IMAP authenticated → Fetch emails → Retrieved from INBOX by default
2. Emails retrieved via IMAP → Classification runs → Classified using existing logic
3. User specifies folder → Emails retrieved from that folder

**Tasks** (11 tasks):

### Tests (TDD - Write First, Seek Approval)

- [X] T033 [P] [US3] Write unit test for folder listing in `tests/unit/test_imap_folders.py` - Test list_folders() returns all Gmail folders
- [X] T034 [P] [US3] Write unit test for folder selection in `tests/unit/test_imap_folders.py` - Test select_folder() changes active folder and returns metadata
- [X] T035 [P] [US3] Write integration test for email retrieval in `tests/integration/test_imap_auth_flow.py` - Test authenticate → select INBOX → fetch emails → verify email structure
- [X] T036 [P] [US3] Write integration test for classification with IMAP in `tests/integration/test_imap_auth_flow.py` - Test IMAP emails → classification pipeline → verify classification works

**Approval Checkpoint**: Present tests T033-T036 to user, explain what each validates, run tests (should FAIL), obtain explicit approval before proceeding

### Implementation

- [X] T037 [US3] Add FolderManager class to `src/gmail_classifier/email/fetcher.py` with __init__(imap_authenticator)
- [X] T038 [P] [US3] Implement list_folders() method in `src/gmail_classifier/email/fetcher.py` - Use IMAPClient.list_folders(), parse into EmailFolder entities, cache results
- [X] T039 [P] [US3] Implement select_folder() method in `src/gmail_classifier/email/fetcher.py` - Use IMAPClient.select_folder(), update session state, return folder metadata (message_count, unread_count)
- [X] T040 [P] [US3] Implement get_folder_status() method in `src/gmail_classifier/email/fetcher.py` - Get folder info without selecting using STATUS command
- [X] T041 [US3] Add fetch_emails() method to `src/gmail_classifier/email/fetcher.py` - Retrieve emails from selected folder in batches (default 10), parse to existing Email entity format
- [X] T042 [US3] Add keepalive mechanism to IMAPAuthenticator in `src/gmail_classifier/auth/imap.py` - Implement keepalive() method that sends NOOP every 10-15 min based on last_activity timestamp
- [X] T043 [US3] Run tests T033-T036 and verify all pass - Ensure 100% pass rate before proceeding

**Completion Criteria**:
- ✅ All unit tests pass (T033-T034)
- ✅ Integration tests pass (T035-T036)
- ✅ Emails retrieved from INBOX and other folders
- ✅ Retrieved emails work with existing classification logic
- ✅ Session keepalive prevents timeouts during classification

---

## Phase 6: CLI Integration & Polish

**Goal**: Complete end-to-end user experience with CLI commands and cross-cutting concerns

**Tasks** (7 tasks):

### CLI Commands

- [X] T044 Add IMAP login command to `src/gmail_classifier/cli/main.py` - Create `login --imap` command that prompts for email/password, calls authenticate(), offers to save credentials
- [X] T045 Add auth status command to `src/gmail_classifier/cli/main.py` - Create `auth-status` command that shows method (OAuth2/IMAP), email, connection state
- [X] T046 Add logout command to `src/gmail_classifier/cli/main.py` - Create `logout` command that disconnects session, clears saved credentials, confirms success

### Documentation & Polish

- [X] T047 [P] Update main README.md with IMAP authentication section - Add setup instructions (enable IMAP, generate app password), usage examples, troubleshooting
- [X] T048 [P] Add AIDEV-NOTE comments in `src/gmail_classifier/auth/imap.py` - Document library choice rationale, label operations via X-GM-LABELS, keepalive strategy
- [X] T049 Run quality gates: `uv run ruff format .` → `uv run ruff check .` → `uv run mypy src` → `uv run pytest -q` - All must pass before commit
- [X] T050 Create example usage script in `examples/imap_auth_example.py` - Demonstrate basic IMAP auth, credential save, auto-login for documentation

**Completion Criteria**:
- ✅ CLI commands work end-to-end
- ✅ Documentation updated
- ✅ All quality gates pass (ruff, mypy, pytest)
- ✅ Example code demonstrates usage

---

## Parallel Execution Examples

### Within User Story 1 (P1)
```bash
# Session 1: Write contract tests
# T010, T011, T012 - IMAP connection tests

# Session 2: Write integration tests
# T013 - Complete auth flow test

# Can run in parallel - different files, no dependencies
```

### Within User Story 2 (P2)
```bash
# Session 1: Write unit tests
# T022, T023, T024 - Credential storage tests

# Session 2: Write integration tests
# T025 - Auto-auth flow test

# Session 3: Implement storage methods
# T027, T028, T029, T030 - store/retrieve/delete/has methods

# T022-T025 can run parallel to T027-T030 (tests vs implementation)
# T027-T030 can run in parallel (different methods, same file - careful coordination)
```

### Within User Story 3 (P3)
```bash
# Session 1: Write unit tests
# T033, T034 - Folder operations tests

# Session 2: Write integration tests
# T035, T036 - Email retrieval and classification tests

# Session 3: Implement folder operations
# T038, T039, T040 - list/select/status methods

# T033-T036 can run parallel to T038-T040 (tests vs implementation)
```

---

## Task Format Validation

✅ **All tasks follow checklist format**:
- Checkbox: `- [ ]`
- Task ID: Sequential (T001-T050)
- [P] marker: Present for parallelizable tasks
- [Story] label: Present for user story tasks (US1, US2, US3)
- Description: Clear action with file path

**Example Task Breakdown**:
```
- [ ] T015 [US1] Implement authenticate() method in `src/gmail_classifier/auth/imap.py` with basic connection logic: IMAPClient('imap.gmail.com', ssl=True), login(), create IMAPSessionInfo
     ^     ^     ^                                                               ^
  Checkbox TaskID Story                                                     File path + Details
```

---

## Summary

**Task Distribution**:
- Setup: 4 tasks
- Foundational: 5 tasks
- User Story 1 (P1): 12 tasks (~24% of total)
- User Story 2 (P2): 11 tasks (~22% of total)
- User Story 3 (P3): 11 tasks (~22% of total)
- Polish: 7 tasks (~14% of total)

**Parallel Opportunities**: 16 tasks marked [P] for parallel execution

**Test Coverage**:
- Contract tests: 3 test files
- Integration tests: 4 test scenarios
- Unit tests: 7 test scenarios
- Total: 14 test tasks (~28% of implementation tasks)

**Recommended Workflow**:
1. Complete Setup + Foundational (T001-T009)
2. Implement User Story 1 with TDD (T010-T021) → **MVP Release**
3. Implement User Story 2 with TDD (T022-T032) → **Enhanced UX Release**
4. Implement User Story 3 with TDD (T033-T043) → **Full Feature Release**
5. Polish and document (T044-T050) → **Production Ready**

---

**Generated**: 2025-11-07
**Next Step**: Begin with Phase 1 (Setup) tasks T001-T004
