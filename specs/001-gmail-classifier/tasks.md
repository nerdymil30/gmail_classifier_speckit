# Tasks: Gmail Classifier & Organizer

**Input**: Design documents from `/specs/001-gmail-classifier/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are NOT requested in the specification, so no test tasks are included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths use `src/gmail_classifier/` as the base package

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan (src/gmail_classifier/ with auth/, models/, services/, cli/, lib/)
- [ ] T002 Initialize Python project with pyproject.toml for uv dependency management
- [ ] T003 [P] Create .env.example template with Gmail OAuth and Claude API placeholders
- [ ] T004 [P] Add dependencies to pyproject.toml (google-api-python-client, anthropic, google-auth-oauthlib, keyring, pytest)
- [ ] T005 [P] Configure .gitignore for credentials.json, token.json, .env files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create configuration management in src/gmail_classifier/lib/config.py (SCOPES, paths, thresholds, batch size)
- [ ] T007 [P] Implement structured logging in src/gmail_classifier/lib/logger.py (sanitize PII, email IDs only)
- [ ] T008 [P] Create SQLite session database schema in src/gmail_classifier/lib/session_db.py (ProcessingSession, ClassificationSuggestion tables)
- [ ] T009 Implement OAuth2 authentication flow in src/gmail_classifier/auth/gmail_auth.py (browser-based, keyring storage)
- [ ] T010 [P] Implement Gmail API client wrapper in src/gmail_classifier/services/gmail_client.py (list labels, list messages, get message, modify labels)
- [ ] T011 [P] Implement exponential backoff utility in src/gmail_classifier/lib/utils.py (rate limit handling, jitter)
- [ ] T012 Create base Email model in src/gmail_classifier/models/email.py (id, thread_id, subject, sender, date, labels, etc.)
- [ ] T013 [P] Create Label model in src/gmail_classifier/models/label.py (id, name, email_count, type)
- [ ] T014 [P] Create ProcessingSession model in src/gmail_classifier/models/session.py (id, status, emails_processed, resume capability)
- [ ] T015 Implement Claude API client setup in src/gmail_classifier/services/claude_client.py (keyring retrieval, API initialization)
- [ ] T016 Create user consent dialog for cloud processing in src/gmail_classifier/cli/consent.py (first-time setup)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Classify Unlabeled Emails (Priority: P1) 🎯 MVP

**Goal**: System analyzes unlabeled emails and suggests appropriate labels based on existing Gmail labels

**Independent Test**: Connect to Gmail account with existing labels and unlabeled emails, run classification, verify suggested labels match user's labeling patterns with confidence scores

### Implementation for User Story 1

- [ ] T017 [P] [US1] Create ClassificationSuggestion model in src/gmail_classifier/models/suggestion.py (email_id, suggested_labels with SuggestedLabel nested type, confidence_category, reasoning, status)
- [ ] T018 [US1] Implement classification prompt builder in src/gmail_classifier/services/classifier.py (include label list, email content, confidence scoring instructions)
- [ ] T019 [US1] Implement single email classification in src/gmail_classifier/services/classifier.py (Claude API call, JSON parsing, label validation)
- [ ] T020 [US1] Implement batch email classification (10 emails per batch) in src/gmail_classifier/services/classifier.py (batch prompt, cost optimization)
- [ ] T021 [US1] Add label validation logic to ensure Claude only suggests from provided label list (convert invalid labels to "No Match")
- [ ] T022 [US1] Implement confidence categorization (high >0.7, medium 0.5-0.7, low 0.3-0.5, no_match <0.3) in src/gmail_classifier/services/classifier.py
- [ ] T023 [US1] Create classification workflow orchestrator in src/gmail_classifier/services/classifier.py (fetch labels, fetch unlabeled emails, classify in batches, save suggestions)
- [ ] T024 [US1] Implement session state persistence (save after each batch) for resume capability
- [ ] T025 [US1] Add progress indicators for batch processing (X of Y emails processed)
- [ ] T026 [US1] Implement dry-run mode in CLI (show suggestions without applying labels)
- [ ] T027 [US1] Create CLI command for classification in src/gmail_classifier/cli/main.py (classify --dry-run --limit N)
- [ ] T028 [US1] Add JSON output format for classification results (--output results.json)
- [ ] T029 [US1] Implement error handling for batch failures (fail entire batch, log for manual retry)
- [ ] T030 [US1] Add logging for all classification operations (email IDs, confidence scores, suggested labels)

**Checkpoint**: At this point, User Story 1 should be fully functional - users can classify emails and see suggestions with confidence scores

---

## Phase 4: User Story 2 - Generate Summary Briefs for Unclassified Emails (Priority: P2)

**Goal**: Provide consolidated summary briefs of emails that don't match existing labels, organized by sender/topic

**Independent Test**: Run classification to identify "No Match" emails, generate summary brief, verify similar emails are grouped with key information and suggested actions

### Implementation for User Story 2

- [ ] T031 [P] [US2] Create SummaryBrief model in src/gmail_classifier/models/summary.py (id, group_type, group_key, email_ids, summary, suggested_action)
- [ ] T032 [US2] Implement summary prompt builder in src/gmail_classifier/services/summarizer.py (include email snippets, grouping instructions)
- [ ] T033 [US2] Implement sender-based grouping logic (simple heuristics, no API call) in src/gmail_classifier/services/summarizer.py
- [ ] T034 [US2] Implement topic-based grouping using Claude API in src/gmail_classifier/services/summarizer.py (semantic understanding)
- [ ] T035 [US2] Implement domain-based grouping logic (extract domain from sender) in src/gmail_classifier/services/summarizer.py
- [ ] T036 [US2] Implement summary brief generation for each group in src/gmail_classifier/services/summarizer.py (2-3 sentence summary, suggested action)
- [ ] T037 [US2] Add suggested action logic (create_new_label, assign_to_existing, delete_all, archive, manual_review)
- [ ] T038 [US2] Create CLI command for summary generation in src/gmail_classifier/cli/main.py (summarize --group-by sender|topic|domain)
- [ ] T039 [US2] Implement summary brief formatting for CLI output (readable, grouped display)
- [ ] T040 [US2] Add summary brief export to JSON format
- [ ] T041 [US2] Integrate summarization with classification workflow (automatically generate after classification completes)
- [ ] T042 [US2] Add logging for summary generation operations

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - users can classify emails AND generate summary briefs

---

## Phase 5: User Story 3 - Review and Approve Classification Suggestions (Priority: P3)

**Goal**: Allow users to review classification suggestions and approve/modify them in bulk before applying labels

**Independent Test**: Generate classification suggestions, display in review interface, approve/modify suggestions, verify changes are queued and applied correctly to Gmail

### Implementation for User Story 3

- [ ] T043 [P] [US3] Create reviewer service in src/gmail_classifier/services/reviewer.py (fetch pending suggestions, group by label)
- [ ] T044 [US3] Implement interactive review UI in CLI in src/gmail_classifier/cli/review.py (show suggestions with [A]pprove/[S]kip/[M]odify/[Q]uit options)
- [ ] T045 [US3] Add suggestion modification logic (change label, mark as "No Label")
- [ ] T046 [US3] Implement bulk approval workflow (approve all high confidence, approve selected)
- [ ] T047 [US3] Add approval confirmation dialog before applying changes
- [ ] T048 [US3] Implement label application to Gmail in src/gmail_classifier/services/gmail_client.py (modify endpoint, batch operations)
- [ ] T049 [US3] Add success/failure tracking for label applications (report which emails succeeded/failed)
- [ ] T050 [US3] Implement retry mechanism for failed label applications
- [ ] T051 [US3] Update suggestion status in database (pending → approved → applied)
- [ ] T052 [US3] Create CLI command for review mode in src/gmail_classifier/cli/main.py (review)
- [ ] T053 [US3] Create CLI command for auto-apply in src/gmail_classifier/cli/main.py (apply --min-confidence 0.8)
- [ ] T054 [US3] Add audit trail logging (all approved/applied suggestions with timestamps)
- [ ] T055 [US3] Implement rollback information logging (for potential future rollback feature)

**Checkpoint**: All user stories should now be independently functional - users can classify, summarize, review, and apply labels

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T056 [P] Create README.md with quickstart guide and usage examples
- [ ] T057 [P] Implement session cleanup command in src/gmail_classifier/cli/main.py (cleanup --older-than 30d)
- [ ] T058 [P] Add session statistics command in src/gmail_classifier/cli/main.py (stats --last-7-days)
- [ ] T059 [P] Implement CSV export for classification results
- [ ] T060 [P] Add resume session command in src/gmail_classifier/cli/main.py (classify --resume session_id)
- [ ] T061 Create CLI setup command for Claude API key in src/gmail_classifier/cli/main.py (setup-claude)
- [ ] T062 Add configuration file support in ~/.gmail_classifier/config.yml (batch sizes, confidence thresholds)
- [ ] T063 Implement quota monitoring and warnings (Gmail API and Claude API)
- [ ] T064 Add verbose/debug logging mode (--debug flag)
- [ ] T065 [P] Code cleanup and refactoring (remove TODOs, consolidate utilities)
- [ ] T066 [P] Security hardening (validate all API responses, sanitize all logs)
- [ ] T067 Run quickstart.md validation (follow steps 1-7, verify all commands work)
- [ ] T068 Add error messages user guide for common issues in README.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Uses "No Match" results from US1 but can be independently tested
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Uses suggestions from US1 but can be independently tested

### Within Each User Story

- Models before services
- Services before CLI commands
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: Foundational Phase

```bash
# Launch all independent foundational tasks together:
Task: "Implement structured logging in src/gmail_classifier/lib/logger.py"
Task: "Create SQLite session database schema in src/gmail_classifier/lib/session_db.py"
Task: "Implement Gmail API client wrapper in src/gmail_classifier/services/gmail_client.py"
Task: "Implement exponential backoff utility in src/gmail_classifier/lib/utils.py"
Task: "Create Label model in src/gmail_classifier/models/label.py"
Task: "Create ProcessingSession model in src/gmail_classifier/models/session.py"
```

## Parallel Example: User Story 1

```bash
# Launch the model creation task (only one model for US1):
Task: "Create ClassificationSuggestion model in src/gmail_classifier/models/suggestion.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (5 tasks)
2. Complete Phase 2: Foundational (11 tasks) - CRITICAL - blocks all stories
3. Complete Phase 3: User Story 1 (14 tasks)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready - users can now classify emails and see suggestions

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (16 tasks)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP! 30 tasks total)
3. Add User Story 2 → Test independently → Deploy/Demo (42 tasks total)
4. Add User Story 3 → Test independently → Deploy/Demo (55 tasks total)
5. Add Polish → Full feature complete (68 tasks total)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (16 tasks)
2. Once Foundational is done:
   - Developer A: User Story 1 (14 tasks)
   - Developer B: User Story 2 (12 tasks)
   - Developer C: User Story 3 (13 tasks)
3. Stories complete and integrate independently
4. Team collaborates on Polish phase (13 tasks)

---

## Task Count Summary

- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 11 tasks (BLOCKS all user stories)
- **Phase 3 (User Story 1 - P1 MVP)**: 14 tasks
- **Phase 4 (User Story 2 - P2)**: 12 tasks
- **Phase 5 (User Story 3 - P3)**: 13 tasks
- **Phase 6 (Polish)**: 13 tasks
- **TOTAL**: 68 tasks

### Tasks by Story

- **User Story 1 (Classification)**: 14 tasks
- **User Story 2 (Summaries)**: 12 tasks
- **User Story 3 (Review/Approve)**: 13 tasks

### Parallel Opportunities Identified

- Setup phase: 3 parallel tasks (T003, T004, T005)
- Foundational phase: 7 parallel tasks (T007, T008, T010, T011, T013, T014)
- User Story 1: 1 parallel task (T017)
- User Story 2: 1 parallel task (T031)
- User Story 3: 1 parallel task (T043)
- Polish phase: 6 parallel tasks (T056, T057, T058, T059, T060, T065, T066)
- **TOTAL PARALLEL**: 19 tasks

### Independent Test Criteria

**User Story 1 (P1)**:
- Connect to Gmail account with existing labels and unlabeled emails
- Run: `python -m gmail_classifier.cli.main classify --dry-run --limit 10`
- Verify: Suggestions displayed with confidence scores matching expected patterns
- Verify: JSON output format works (`--output results.json`)
- Verify: "No Match" flagged for emails that don't fit any label

**User Story 2 (P2)**:
- After running US1 classification
- Run: `python -m gmail_classifier.cli.main summarize --group-by sender`
- Verify: "No Match" emails grouped by sender/topic/domain
- Verify: 2-3 sentence summaries generated for each group
- Verify: Suggested actions provided (create_new_label, archive, etc.)

**User Story 3 (P3)**:
- After running US1 classification
- Run: `python -m gmail_classifier.cli.main review`
- Verify: Interactive interface displays suggestions
- Verify: Can approve/skip/modify individual suggestions
- Verify: Batch approval applies labels to Gmail successfully
- Verify: Success/failure report shows which emails were labeled

---

## Suggested MVP Scope

**Recommendation**: Implement User Story 1 (Phase 1 + Phase 2 + Phase 3) = 30 tasks

This provides immediate value:
- Users can authenticate with Gmail
- Users can see classification suggestions for unlabeled emails
- Users can review suggestions in dry-run mode
- Users can export suggestions to JSON for manual review
- System respects read-only constraint (no labels applied yet)

**Estimated Time**: 2-3 days for solo developer (foundation + classification engine + CLI)

**Next Increments**:
- User Story 2 (Summaries): +12 tasks, +1 day
- User Story 3 (Review/Apply): +13 tasks, +1 day
- Polish: +13 tasks, +1 day

**Total Feature**: 68 tasks, 5-7 days for solo developer

---

## Notes

- Tests are NOT included per spec.md (no TDD requirement)
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Privacy constraint: No email content persistence beyond session
- Security constraint: API keys in keyring, credentials in .env (gitignored)
- Read-only constraint: No deletion capability (classification and suggestion only)
