# Claude API Contract: Gmail Classifier & Organizer

**Feature**: Gmail Classifier & Organizer
**Created**: 2025-11-05
**Purpose**: Define Claude API integration contracts and expectations

## Authentication & Setup

### API Key Management

**Library**: `anthropic` (official Python SDK)

**API Key Storage**:
- Store in system keyring using `keyring` library (not environment variables or files)
- Never commit API key to version control
- Retrieve from keyring for each session

**Setup Flow**:
1. User provides API key during first-time setup
2. System validates key by making test API call
3. Store validated key in system keyring
4. Retrieve from keyring for subsequent sessions

**Keyring Integration**:
```python
import keyring

# Store API key (first-time setup)
keyring.set_password("gmail_classifier", "anthropic_api_key", api_key)

# Retrieve API key (subsequent sessions)
api_key = keyring.get_password("gmail_classifier", "anthropic_api_key")
```

**Error Handling**:
- Invalid API key → Clear error message, prompt re-entry
- API key not found → Trigger first-time setup flow
- Keyring access denied → Fallback to secure environment variable

---

## API Endpoints

### 1. Email Classification

**Purpose**: Classify unlabeled email and suggest appropriate Gmail label

**Endpoint**: `POST https://api.anthropic.com/v1/messages`

**Model**: `claude-3-haiku-20240307`

**Request Structure**:
```python
import anthropic

client = anthropic.Anthropic(api_key=api_key)

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=200,
    messages=[{
        "role": "user",
        "content": f"""You are an email classification assistant. Given an email, suggest the most appropriate label from the provided list.

Available labels: Finance, Work, Personal, Shopping

Email to classify:
Subject: Your monthly bank statement is ready
Body: Your statement for January 2025 is now available to view online. Login to your account to access it.

Instructions:
1. Analyze the email content and determine which label best fits
2. Only suggest labels from the provided list above
3. Provide a confidence score (0.0-1.0) based on how well the email matches the label
4. If confidence is below 0.3, return "No Match"
5. Provide brief reasoning for your choice

Response format (JSON):
{{
  "suggested_label": "label_name or No Match",
  "confidence": 0.85,
  "reasoning": "Brief explanation"
}}"""
    }]
)
```

**Response Structure**:
```json
{
  "id": "msg_01XYZ...",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "{\"suggested_label\": \"Finance\", \"confidence\": 0.92, \"reasoning\": \"Email is from bank about monthly statement, clearly financial content\"}"
    }
  ],
  "model": "claude-3-haiku-20240307",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 245,
    "output_tokens": 45
  }
}
```

**Parsing Logic**:
```python
import json

# Extract text from response
response_text = response.content[0].text

# Parse JSON
result = json.loads(response_text)

# Validate label is in allowed list
if result['suggested_label'] not in available_labels and result['suggested_label'] != "No Match":
    result['suggested_label'] = "No Match"
    result['reasoning'] += " (Invalid label suggested, marked as No Match)"
```

**Token Usage**:
- Input: ~200-300 tokens (labels list + email content + instructions)
- Output: ~30-50 tokens (JSON response)
- Cost per request: ~$0.000075 (0.25K tokens input × $0.25/M + 0.05K tokens output × $1.25/M)

**Rate Limits**:
- Tier 1 (default): 50,000 requests per minute
- Tier 1 (default): 25,000,000 tokens per month
- Sufficient for 100,000+ classifications per month

**Error Responses**:
- 400 Bad Request → Invalid prompt format
- 401 Unauthorized → Invalid API key
- 429 Rate Limit → Exponential backoff (extremely rare with these limits)
- 500 Internal Error → Retry up to 3 times
- 529 Overloaded → Wait and retry

---

### 2. Batch Email Classification

**Purpose**: Classify multiple emails (up to 10) in single API call for efficiency

**Request Structure**:
```python
emails_batch = [
    {"subject": "Meeting tomorrow", "body": "Let's meet at 10am..."},
    {"subject": "Invoice #12345", "body": "Your payment of $500..."},
    # ... up to 10 emails
]

email_list = "\n\n".join([
    f"Email {i+1}:\nSubject: {email['subject']}\nBody: {email['body'][:500]}"
    for i, email in enumerate(emails_batch)
])

prompt = f"""You are an email classification assistant. Classify each email below with the most appropriate label.

Available labels: {', '.join(available_labels)}

Emails to classify:
{email_list}

For each email, provide:
1. Suggested label (from available labels only, or "No Match" if none fit)
2. Confidence score (0.0-1.0)
3. Brief reasoning

Response format (JSON array):
[
  {{"email_num": 1, "suggested_label": "Work", "confidence": 0.85, "reasoning": "..."}},
  {{"email_num": 2, "suggested_label": "Finance", "confidence": 0.92, "reasoning": "..."}}
]"""

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1000,
    messages=[{"role": "user", "content": prompt}]
)
```

**Token Usage (10 emails)**:
- Input: ~2000-3000 tokens (labels + 10 emails + instructions)
- Output: ~300-500 tokens (JSON array with 10 results)
- Cost per batch: ~$0.00125 (3K input + 0.5K output)
- **Cost savings**: ~40% cheaper than 10 individual requests

**Batch Size Recommendation**: 10 emails per batch
- Balances cost efficiency with context window usage
- Stays well within 200K context limit
- Allows clear error attribution if batch fails

---

### 3. Summary Brief Generation

**Purpose**: Generate consolidated summary for "No Match" emails, grouped by similarity

**Request Structure**:
```python
no_match_emails = [
    {"sender": "news@tech.com", "subject": "Daily Newsletter", "body": "Top tech news..."},
    {"sender": "news@tech.com", "subject": "Weekly Digest", "body": "This week in tech..."},
    # ... more unclassified emails
]

email_snippets = "\n\n".join([
    f"Email {i+1}:\nFrom: {email['sender']}\nSubject: {email['subject']}\nSnippet: {email['body'][:200]}"
    for i, email in enumerate(no_match_emails)
])

prompt = f"""Analyze these unclassified emails and group them by similarity (sender/topic).

Emails:
{email_snippets}

For each group, provide:
1. Group type (sender/topic/domain)
2. Which email numbers belong to this group
3. 2-3 sentence summary of the group
4. Suggested action (create_new_label/archive/delete_all/manual_review)

Response format (JSON):
[
  {{
    "group_type": "sender",
    "group_key": "newsletters@company.com",
    "email_numbers": [1, 3, 5],
    "summary": "Marketing newsletters from Company XYZ...",
    "suggested_action": "create_new_label"
  }}
]"""

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1500,
    messages=[{"role": "user", "content": prompt}]
)
```

**Token Usage (20 emails)**:
- Input: ~2500-3500 tokens (20 email snippets + instructions)
- Output: ~400-600 tokens (grouped summaries)
- Cost per summary: ~$0.0015 (3.5K input + 0.5K output)

**Frequency**: Generated once per classification session after all "No Match" emails identified

---

## Rate Limiting Strategy

### Quota Management

**Claude API Quotas** (Tier 1 - default):
- Requests per minute: 50,000 RPM (extremely high - unlikely to hit)
- Tokens per month: 25,000,000 TPM
- **Critical**: Monthly token limit is the constraint for high-volume usage

**Token Cost Calculation**:
```
For 1000 emails classified:
- 100 batches of 10 emails each
- Input: 100 × 3000 tokens = 300K tokens
- Output: 100 × 500 tokens = 50K tokens
- Total: 350K tokens used

Monthly limit: 25M tokens
Max emails per month (classification only): ~70,000 emails
```

**Processing Rate**:
```
For classifying 100 emails (10 batches):
- API latency: ~200-500ms per request × 10 batches = 2-5 seconds
- Plus Gmail API fetch time: ~3 minutes
- Total: ~3-4 minutes for 100 emails ✅ Meets <5 min requirement
```

### Exponential Backoff

```python
import time
import random

def exponential_backoff_with_jitter(attempt, max_attempts=5):
    """Calculate backoff delay with jitter."""
    if attempt >= max_attempts:
        raise Exception("Max retry attempts exceeded")

    # Exponential backoff: 1s, 2s, 4s, 8s, 16s
    delay = min(2 ** attempt, 32)

    # Add jitter to prevent thundering herd
    jitter = random.uniform(0, delay * 0.1)

    time.sleep(delay + jitter)
```

**Apply backoff for**:
- 429 Rate Limit Exceeded (retry up to 5 times)
- 500/502/503 Server errors (retry up to 3 times)
- 529 Overloaded (retry up to 3 times with longer backoff)

---

## Error Handling Matrix

| Error Code | Meaning | Action | Retry? | User Message |
|------------|---------|--------|--------|--------------|
| 400 | Bad Request | Log error, fail batch | No | "Invalid request format. Please contact support." |
| 401 | Unauthorized | Prompt API key re-entry | No | "API key invalid. Please re-enter your Anthropic API key." |
| 429 | Rate Limit | Exponential backoff | Yes (5 attempts) | "API rate limit reached. Retrying..." |
| 500 | Internal Error | Exponential backoff | Yes (3 attempts) | "Claude API error. Retrying..." |
| 529 | Overloaded | Wait and retry | Yes (3 attempts) | "Claude API busy. Retrying in {delay}s..." |
| Network | Timeout/Connection | Exponential backoff | Yes (3 attempts) | "Network error. Retrying..." |

**Batch Failure Handling** (per user requirement):
- If ANY email in batch fails after retries → Mark entire batch as failed
- User sees: "Batch failed: {error_message}. Please retry manually."
- Log which batch failed (email IDs) for manual retry
- No partial batch completion

---

## Testing Strategy

### Mock Responses

**For Contract Tests**:
```python
import pytest
from unittest.mock import Mock, patch, MagicMock

@pytest.fixture
def mock_claude_client():
    """Mock Anthropic client for testing."""
    with patch('anthropic.Anthropic') as mock:
        client = Mock()
        mock.return_value = client

        # Mock successful classification response
        client.messages.create.return_value = Mock(
            id="msg_test123",
            content=[Mock(
                type="text",
                text='{"suggested_label": "Finance", "confidence": 0.85, "reasoning": "Bank statement email"}'
            )],
            usage=Mock(input_tokens=250, output_tokens=45)
        )

        yield client

def test_classify_email(mock_claude_client):
    """Test email classification with mocked API."""
    classifier = ClaudeEmailClassifier(api_key="test-key")

    result = classifier.classify_email(
        email_content="Your bank statement is ready",
        available_labels=["Finance", "Work", "Personal"],
        subject="Monthly Statement"
    )

    assert result['suggested_label'] == 'Finance'
    assert result['confidence'] == 0.85
    assert mock_claude_client.messages.create.called

def test_api_error_handling(mock_claude_client):
    """Test API error handling."""
    from anthropic import APIError

    mock_claude_client.messages.create.side_effect = APIError("Rate limit exceeded")

    classifier = ClaudeEmailClassifier(api_key="test-key")

    with pytest.raises(Exception, match="Claude API error"):
        classifier.classify_email(
            email_content="Test",
            available_labels=["Finance"],
            subject="Test"
        )

def test_label_validation(mock_claude_client):
    """Test that invalid labels are caught and corrected."""
    # Mock response with invalid label
    mock_claude_client.messages.create.return_value = Mock(
        content=[Mock(
            text='{"suggested_label": "InvalidLabel", "confidence": 0.9, "reasoning": "test"}'
        )]
    )

    classifier = ClaudeEmailClassifier(api_key="test-key")
    result = classifier.classify_email(
        email_content="Test",
        available_labels=["Finance", "Work"]
    )

    # Should be converted to "No Match"
    assert result['suggested_label'] == 'No Match'
    assert 'Invalid label' in result['reasoning']
```

**Offline Mode**:
- Use mocked client for all tests
- Save sample API responses as JSON fixtures
- Load fixtures instead of making real API calls
- Enables development without API key or internet

---

## Security Considerations

1. **API Key Protection**:
   - Store in system keyring (encrypted by OS)
   - Never log API key or include in error messages
   - Never commit to version control
   - Rotate if accidentally exposed

2. **Data Privacy**:
   - Full email content sent to Anthropic API (user consent required)
   - Anthropic's data policy: Not used for training, not retained after response
   - Never log email content (only IDs and metadata)
   - Clear email content from memory after classification

3. **User Consent**:
   - Display consent dialog before first API call
   - Explain data being sent: "Full email content (subject, body, sender) will be sent to Anthropic API for classification"
   - Store consent acknowledgment in session database
   - Provide opt-out option (exits classification)

4. **Request Validation**:
   - Validate all labels in API response against provided list
   - Sanitize email content before sending (remove attachments, images)
   - Validate JSON responses with schema

5. **Rate Limiting**:
   - Implement exponential backoff to avoid abuse
   - Monitor token usage, warn user if approaching monthly limit
   - Graceful degradation if quota exceeded

---

## Example Integration Code

```python
import anthropic
import keyring
import json

class ClaudeAPIClient:
    def __init__(self):
        """Initialize Claude API client with secure key retrieval."""
        self.api_key = keyring.get_password("gmail_classifier", "anthropic_api_key")
        if not self.api_key:
            raise Exception("Anthropic API key not found. Please run setup.")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-3-haiku-20240307"

    def classify_email(self, email_content, available_labels, subject=""):
        """Classify single email."""
        prompt = self._build_classification_prompt(email_content, available_labels, subject)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            result = json.loads(response.content[0].text)

            # Validate label
            if result['suggested_label'] not in available_labels and result['suggested_label'] != "No Match":
                result['suggested_label'] = "No Match"
                result['reasoning'] += " (Invalid label)"

            return result

        except anthropic.APIError as e:
            raise Exception(f"Claude API error: {str(e)}")

    def _build_classification_prompt(self, email_content, available_labels, subject):
        """Build classification prompt."""
        return f"""You are an email classification assistant. Given an email, suggest the most appropriate label from the provided list.

Available labels: {', '.join(available_labels)}

Email to classify:
Subject: {subject}
Body: {email_content}

Instructions:
1. Analyze the email content and determine which label best fits
2. Only suggest labels from the provided list above
3. Provide a confidence score (0.0-1.0) based on how well the email matches the label
4. If confidence is below 0.3, return "No Match"
5. Provide brief reasoning for your choice

Response format (JSON):
{{
  "suggested_label": "label_name or No Match",
  "confidence": 0.85,
  "reasoning": "Brief explanation"
}}"""
```

---

## References

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude 3 Models](https://docs.anthropic.com/claude/docs/models-overview)
- [API Rate Limits](https://docs.anthropic.com/claude/reference/rate-limits)
- [Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
