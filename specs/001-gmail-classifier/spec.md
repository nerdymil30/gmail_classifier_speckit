# Feature Specification: Gmail Classifier & Organizer

**Feature Branch**: `001-gmail-classifier`
**Created**: 2025-11-05
**Status**: Draft
**Input**: User description: "Build an application that can help me organize my gmail based on the existing labels and emails that don't fit my current framework should be consolidated and summarized like a brief, based on which they can be deleted or redirected. You are building a classifier system, you don't have the authority to delete anything"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Classify Unlabeled Emails (Priority: P1)

As a Gmail user, I want the system to analyze my unlabeled emails and suggest which existing label(s) they should be assigned to, so that I can quickly organize my inbox based on my established categorization system.

**Why this priority**: This is the core value proposition - helping users organize emails that don't fit their current framework. Without this, no other features provide value.

**Independent Test**: Can be fully tested by connecting to a Gmail account with existing labels and unlabeled emails, running classification, and verifying that suggested labels match the user's labeling patterns. Delivers immediate value by identifying where each email belongs.

**Acceptance Scenarios**:

1. **Given** I have Gmail account with existing labels like "Finance", "Personal", "Work Projects", **When** system analyzes an unlabeled email about a bank statement, **Then** system suggests "Finance" label with confidence score
2. **Given** I have 50 unlabeled emails in my inbox, **When** I run the classifier, **Then** system provides label suggestions for all 50 emails with confidence scores
3. **Given** an email that matches multiple label categories, **When** system classifies it, **Then** system suggests multiple labels ranked by relevance
4. **Given** an email that doesn't match any existing label patterns, **When** system classifies it, **Then** system flags it as "No Match" for review

---

### User Story 2 - Generate Summary Briefs for Unclassified Emails (Priority: P2)

As a Gmail user, I want to receive a consolidated summary brief of emails that don't match my existing label framework, organized by similarity or topic, so that I can decide whether to delete them, create new labels, or redirect them appropriately.

**Why this priority**: This addresses the "consolidate and summarize like a brief" requirement. Once users know what doesn't fit (P1), they need organized summaries to make decisions. This is essential for users with many unclassifiable emails.

**Independent Test**: Can be tested by providing emails marked as "No Match" from P1, generating a summary brief, and verifying that similar emails are grouped together with key information extracted. Delivers value by reducing decision-making time.

**Acceptance Scenarios**:

1. **Given** 20 emails flagged as "No Match" from classification, **When** I request a summary brief, **Then** system groups similar emails and provides a digest with: sender, subject, date, and 1-2 sentence summary per email
2. **Given** emails from the same sender/domain in "No Match" category, **When** summary is generated, **Then** emails are grouped by sender with aggregate statistics (count, date range)
3. **Given** emails on similar topics in "No Match" category, **When** summary is generated, **Then** emails are grouped by detected topic with relevance scores
4. **Given** a summary brief is displayed, **When** I review it, **Then** system provides suggested actions for each group: "Delete All", "Create New Label", "Assign to Existing Label", "Archive"

---

### User Story 3 - Review and Approve Classification Suggestions (Priority: P3)

As a Gmail user, I want to review the classification suggestions before they are applied, and approve or modify them in bulk, so that I maintain control over my email organization and can correct any misclassifications.

**Why this priority**: This ensures user control and builds trust in the system. While important, users can still get value from P1 (seeing suggestions) and P2 (summaries) without this approval workflow. This is about polish and control.

**Independent Test**: Can be tested by generating classification suggestions from P1, displaying them in a review interface, allowing bulk approval/modification, and verifying changes are queued correctly. Delivers value by preventing errors and giving users confidence.

**Acceptance Scenarios**:

1. **Given** system has generated 30 label suggestions, **When** I open the review interface, **Then** I see all suggestions grouped by proposed label with ability to approve all, approve selected, or modify
2. **Given** I disagree with a classification suggestion, **When** I modify it in the review interface, **Then** system allows me to select a different label or mark as "No Label"
3. **Given** I have reviewed and approved suggestions, **When** I click "Apply Changes", **Then** system applies approved labels to Gmail emails (via Gmail API) and reports success/failures
4. **Given** some label applications fail due to API errors, **When** batch completes, **Then** system reports which emails succeeded and which failed with reasons

---

### Edge Cases

- What happens when a Gmail account has no existing labels? System should notify user that classification requires at least one label to learn patterns from, and suggest creating labels first.
- What happens when Gmail API quota is exceeded during classification? System should pause processing, notify user of quota limit, and allow resuming from last processed email.
- What happens when an email has very little content (just "Thanks!")? System should flag these as "Insufficient Content" rather than forcing a classification.
- What happens when user's Gmail account has thousands of unlabeled emails? System should support batch processing with progress indicators and allow processing in chunks (e.g., 100 at a time).
- What happens when Gmail authentication expires during processing? System should detect auth failure, prompt user to re-authenticate, and resume from last position.
- What happens when an email is written in a non-English language? System should attempt classification on English content only. Non-English emails should be flagged as "Insufficient Content" or "Unknown Language" for manual review.
- What happens if user declines cloud processing consent? System should display clear error message explaining that classification requires Claude API access, and offer option to exit or review consent policy. No classification can proceed without consent.
- What happens when Claude API is unavailable or fails during batch processing? System should mark entire batch as failed, display clear error message with API error details, and allow user to manually retry the full batch when API is available again. No partial batch processing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST connect to user's Gmail account using OAuth2 authentication with read-only permissions (no delete capability)
- **FR-001a**: System MUST obtain explicit user consent before first use, acknowledging that full email content (subject, body, sender, metadata) will be sent to Anthropic Claude API for classification purposes
- **FR-002**: System MUST retrieve user's existing Gmail labels to understand the current organizational framework
- **FR-003**: System MUST identify unlabeled emails (emails without any user-created labels)
- **FR-004**: System MUST analyze email content (subject, body, sender, metadata) using Claude SDK (Haiku model) to determine similarity to existing labeled emails and suggest appropriate labels; MUST include complete list of available Gmail labels in each API request to constrain suggestions to existing labels only
- **FR-005**: System MUST suggest appropriate label(s) for each unlabeled email with confidence scores (0-100%)
- **FR-006**: System MUST flag emails that don't match any existing label pattern as "No Match" candidates
- **FR-007**: System MUST generate summary briefs for "No Match" emails using Claude SDK (Haiku model) to group by topic/similarity and generate natural language summaries; sender/domain grouping uses simple heuristics (no API call needed)
- **FR-008**: System MUST provide action suggestions for each email or email group: suggested label, "No Match", or "Insufficient Content"
- **FR-009**: System MUST allow users to review classification suggestions before applying any changes
- **FR-010**: System MUST apply approved label assignments to Gmail via API (with user confirmation)
- **FR-011**: System MUST respect Gmail API rate limits and quotas with exponential backoff
- **FR-012**: System MUST maintain a processing log showing which emails were processed, suggested labels, and final actions
- **FR-013**: System MUST handle authentication errors gracefully with clear re-authentication prompts
- **FR-014**: System MUST support batch processing in groups of 10 emails with progress indicators; users manually trigger classification runs rather than automatic/real-time processing
- **FR-015**: System MUST operate in read-only mode - NO deletion capability (classification and suggestion only)
- **FR-016**: System MUST fail entire batch if Claude API fails for any email in the batch; user must manually retry the full batch (no partial batch completion)
- **FR-017**: System MUST validate that Claude API responses only contain labels from the provided label list; if Claude suggests a label not in the list, treat as "No Match" and log warning

### Key Entities

- **Email**: Represents a Gmail message with attributes: subject, body content, sender, recipients, date, current labels, thread ID
- **Label**: Represents a Gmail label (user-created category) with attributes: label name, email count, usage pattern
- **Classification Suggestion**: Represents a proposed label assignment with attributes: email reference, suggested label(s), confidence score, reasoning
- **Summary Brief**: Represents a consolidated report with attributes: email group (by sender/topic), email count, key metadata, suggested action
- **Processing Session**: Represents a classification run with attributes: start time, emails processed, suggestions generated, status (in-progress/complete/paused)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can classify 100 unlabeled emails in under 5 minutes (including review time)
- **SC-002**: Classification suggestions achieve at least 70% accuracy based on user's historical labeling patterns
- **SC-003**: 80% of users successfully complete their first classification session without errors or confusion
- **SC-004**: Summary briefs reduce decision-making time by 50% compared to manually reviewing individual "No Match" emails
- **SC-005**: System processes emails at minimum rate of 20 emails per minute (accounting for API limits)
- **SC-006**: Zero incidents of unauthorized email deletion or modification (strict read-only enforcement)
- **SC-006a**: 100% of users acknowledge cloud processing consent before any email content is sent to Claude API
- **SC-007**: User can resume interrupted classification session within 30 seconds of re-authentication

## Clarifications

### Session 2025-11-05

- Q: Which AI service should be used for email classification? → A: Claude SDK with Haiku model (cloud-based classification via Anthropic API)
- Q: Should classification run in batch mode or real-time per email? → A: Batch mode (10 emails at a time) - User manually triggers classification runs, processes in batches of 10, generates suggestions, user reviews and approves
- Q: How much email content should be sent to Claude API for classification? → A: Send full email content (subject, body, sender, metadata) to Claude API for best classification accuracy; requires user consent acknowledgment that emails are processed via Anthropic cloud API
- Q: How should Claude API failures be handled during batch processing? → A: Fail entire batch and require manual retry - if Claude API fails for any email in a batch of 10, mark entire batch as failed and user must manually retry the full batch (simple, predictable behavior)
- Q: How should summary briefs for "No Match" emails be generated? → A: Use Claude API (Haiku) for summaries - Generate high-quality natural language summaries for each email group using Claude API, providing consistent quality with classification approach
- Q: How should email similarity detection work for topic-based grouping? → A: Use Claude API for grouping - Send all "No Match" emails to Claude and ask it to group by topic/similarity, leveraging Claude's semantic understanding without additional ML dependencies
- Q: How should label suggestions be constrained during classification? → A: Include complete list of available Gmail labels in each Claude API request; Claude must only suggest from this provided label list (no hallucinated or new labels)

### Assumptions

- Users have at least 3-5 existing Gmail labels with historically labeled emails to establish classification patterns
- System supports English-only classification; non-English emails will be flagged for manual review
- Gmail API quotas are sufficient for typical user workload (250-500 emails per session)
- System operates in manual batch mode (10 emails per batch) rather than real-time monitoring; users trigger classification runs when desired
- Full email content (subject, body, sender, metadata) is sent to Claude API for classification; user consent required and explicitly acknowledged before first use
- Classification relies on Anthropic Claude API availability and quotas; offline/local classification not supported
- Classification accuracy improves over time as more emails are labeled (learning from user corrections)
