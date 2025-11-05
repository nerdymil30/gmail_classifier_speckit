# Gmail Classification Project: Technology Research

**Research Date:** January 2025
**Python Version:** 3.11+
**Project Type:** CLI Application for Gmail Email Classification

---

## Executive Summary

This document provides comprehensive research on two critical technology choices for a Gmail classification Python project:

1. **Gmail API Integration Library**: Recommendation is **google-api-python-client** (official library)
2. **Email Classification & Summarization**: Recommendation is **anthropic SDK** (Claude API with Haiku model) for AI-powered semantic classification and summary generation

---

## Research Task 1: Gmail API Python Integration

### Overview of Options

Three primary approaches were evaluated for Gmail API integration:

1. **google-api-python-client** - Official Google library
2. **simplegmail** - Third-party wrapper library
3. **Direct REST API** - Manual HTTP requests

### Detailed Comparison

#### Option 1: google-api-python-client (RECOMMENDED)

**Official Documentation:** https://github.com/googleapis/google-api-python-client

**Advantages:**
- Official Google library with full API coverage and long-term support
- Active maintenance and timely updates for API changes
- Uses modern authentication libraries (`google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`)
- Complete access to all Gmail API features and endpoints
- Large community support and extensive documentation
- Better suited for production environments
- Recommended by Google for enterprise applications

**Disadvantages:**
- More verbose code for simple operations
- Steeper learning curve - requires understanding Gmail API structure
- More boilerplate code needed for authentication and common tasks
- No high-level convenience methods

**Installation:**
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

**Best Practices:**

1. **OAuth2 Authentication (Required as of Sept 2024)**
   - Enhanced Security (OAuth2) is mandatory for Google Workspace
   - Store credentials in `credentials.json` (from Google Cloud Console)
   - Token auto-generated and saved in `token.json` after first authorization
   - Token refresh handled automatically by the library

2. **Rate Limiting and Quotas**
   - Daily quota: 1,000,000,000 quota units per day
   - Per-user rate limit: 250 quota units per user per second (moving average)
   - Different operations consume different quota units
   - Error code 429: "User-rate limit exceeded"

3. **Error Handling with Exponential Backoff**
   ```python
   import time
   from googleapiclient.errors import HttpError

   def execute_with_backoff(request, max_retries=5):
       for retry in range(max_retries):
           try:
               return request.execute()
           except HttpError as error:
               if error.resp.status == 429:
                   wait_time = 2 ** retry
                   print(f"Rate limit hit, waiting {wait_time}s...")
                   time.sleep(wait_time)
               else:
                   raise
       raise Exception("Max retries exceeded")
   ```

4. **Batch Requests**
   - Combine multiple API calls into one HTTP request
   - Reduces overhead and quota consumption
   - Particularly useful for fetching multiple emails

5. **Local Caching**
   - Cache email metadata (message IDs, labels) locally
   - Minimize unnecessary API calls
   - Refresh only when needed

6. **Push Notifications**
   - Use Gmail push notifications instead of polling
   - Eliminates network and compute costs of constant polling
   - More efficient for real-time updates

**Example Code Pattern:**
```python
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os.path

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def get_labels(service):
    """Fetch all Gmail labels."""
    try:
        results = service.users().labels().list(userId='me').execute()
        return results.get('labels', [])
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def list_messages(service, query='', max_results=10):
    """List messages matching query."""
    try:
        results = service.users().messages().list(
            userId='me', q=query, maxResults=max_results
        ).execute()
        return results.get('messages', [])
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def get_message(service, msg_id):
    """Retrieve a specific message."""
    try:
        message = service.users().messages().get(
            userId='me', id=msg_id, format='full'
        ).execute()
        return message
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None
```

**Testing and Mocking:**

For testing, use `pytest` with `unittest.mock` or `pytest-mock`:

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError

def test_get_labels_success(mock_gmail_service):
    """Test successful label retrieval."""
    # Mock the service
    mock_service = Mock()
    mock_service.users().labels().list().execute.return_value = {
        'labels': [
            {'id': 'INBOX', 'name': 'INBOX'},
            {'id': 'SPAM', 'name': 'SPAM'}
        ]
    }

    labels = get_labels(mock_service)
    assert len(labels) == 2
    assert labels[0]['name'] == 'INBOX'

def test_get_labels_with_error(mock_gmail_service):
    """Test error handling."""
    mock_service = Mock()
    mock_service.users().labels().list().execute.side_effect = HttpError(
        resp=Mock(status=500), content=b'Internal error'
    )

    labels = get_labels(mock_service)
    assert labels == []

@pytest.fixture
def mock_gmail_service():
    """Fixture to provide mocked Gmail service."""
    with patch('googleapiclient.discovery.build') as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        yield mock_service
```

**Best Practices for Testing:**
- Use `autospec=True` with patches to ensure mocks respect function signatures
- Mock at the service level, not the HTTP transport level
- Use parameterized tests (`@pytest.mark.parametrize`) for different scenarios
- Test both success and error cases
- Verify mock calls with `assert_called_with()` or `assert_called_once_with()`
- Create reusable fixtures for common mock objects

---

#### Option 2: simplegmail

**GitHub:** https://github.com/jeremyephron/simplegmail
**PyPI:** https://pypi.org/project/simplegmail/

**Advantages:**
- Simpler, more intuitive API for common operations
- High-level convenience methods: `get_unread_inbox()`, `get_starred_messages()`
- Less boilerplate code for basic tasks
- Good for rapid prototyping
- Automatic handling of common Gmail operations

**Disadvantages:**
- **Uses deprecated `oauth2client` library** (replaced by `google-auth`)
- Wrapper around google-api-python-client (adds extra abstraction layer)
- Additional dependencies: beautifulsoup4, python-dateutil, lxml
- Less flexibility for advanced/custom operations
- Smaller community, less frequent updates
- **Not recommended for production** due to deprecated dependencies
- May not support newest Gmail API features

**Installation:**
```bash
pip install simplegmail
```

**Example Usage:**
```python
from simplegmail import Gmail

gmail = Gmail()  # First run opens browser for auth

# Simple operations
unread = gmail.get_unread_inbox()
starred = gmail.get_starred_messages()

# Send email with attachment
gmail.send_message(
    to='recipient@example.com',
    subject='Test Email',
    msg_plain='This is the email body',
    attachments=['file.pdf']
)
```

**Verdict:** Not recommended for this project due to use of deprecated authentication libraries and limited production support.

---

#### Option 3: Direct REST API

**Official Documentation:** https://developers.google.com/gmail/api/reference/rest

**Advantages:**
- Complete control over all requests
- No dependency on third-party libraries (except `requests`)
- Understand exactly what's happening under the hood
- Can optimize for specific use cases

**Disadvantages:**
- Manual handling of OAuth2 flow
- Manual request formatting and response parsing
- More code to write and maintain
- Manual error handling and retry logic
- No automatic token refresh
- Reinventing the wheel - not recommended by Google

**Verdict:** Not recommended. The official client library provides all the benefits of REST API control with better abstractions and OAuth2 handling.

---

### Final Recommendation: google-api-python-client

**Why:**
1. Official Google library with long-term support
2. Modern authentication (google-auth, not deprecated oauth2client)
3. Full API coverage for all Gmail operations
4. Production-ready with active maintenance
5. Better for OAuth2, rate limiting, and error handling
6. Large community and extensive documentation

**When to Use Alternatives:**
- **simplegmail**: Only for quick prototypes or learning projects (not production)
- **REST API**: Never, unless you have very specific requirements not met by the client library

---

## Research Task 2: Email Classification & Summarization

### Overview of Options

Three primary approaches were evaluated for email classification and summarization:

1. **anthropic SDK (Claude API)** - Cloud-based AI classification and summarization
2. **sentence-transformers** - Local semantic embeddings
3. **scikit-learn** - TF-IDF with cosine similarity

### Detailed Comparison

#### Option 1: anthropic SDK - Claude API with Haiku Model (RECOMMENDED)

**Official Documentation:** https://docs.anthropic.com/

**Advantages:**
- Excellent semantic understanding via state-of-the-art LLM
- No local ML model needed (cloud-based)
- Handles both classification AND summarization with single API
- Can enforce label constraints naturally (provide label list in prompt)
- High-quality natural language summaries
- No training data required - works with few-shot examples
- Automatically handles topic-based grouping and similarity detection
- Easy confidence scoring via prompt engineering
- Supports batch processing for cost optimization
- Consistent AI approach for all semantic tasks

**Disadvantages:**
- Requires internet connection (cloud API)
- API costs per request (~$0.00025 per 1K tokens for Haiku)
- Latency (~200-500ms per request)
- Requires user consent for sending email content to Anthropic
- Dependent on Anthropic API availability
- Need API key management and secure storage

**Best For:**
- Projects requiring high-quality semantic understanding
- When summarization is needed alongside classification
- Small to medium email volumes (100-1000 emails per session)
- When label constraint enforcement is critical
- Projects that can handle cloud processing with user consent

**Installation:**
```bash
pip install anthropic
```

**API Cost Analysis:**
- **Model**: Claude 3 Haiku
- **Pricing**: $0.25 per million input tokens, $1.25 per million output tokens
- **Average email**: ~500 tokens (subject + body)
- **Classification prompt**: ~200 tokens (labels list + instructions)
- **Cost per email classification**: ~$0.000175 (0.7K tokens input + small output)
- **Cost for 100 emails**: ~$0.0175 (less than 2 cents)
- **Cost for 1000 emails**: ~$0.175 (about 18 cents)
- **Summary generation**: ~$0.0003 per email group
- **Monthly budget for 500 emails/month**: ~$0.10 (10 cents)

**Best Practices:**

1. **Batch Processing**
   - Process 10 emails per batch to optimize API usage
   - Include all 10 emails in single API call when possible
   - Reduces per-request overhead

2. **Label Constraint Enforcement**
   - Include complete label list in system prompt
   - Explicitly instruct Claude to only suggest from provided labels
   - Validate responses to ensure compliance

3. **User Consent**
   - Display clear consent dialog before first use
   - Explain that full email content is sent to Anthropic API
   - Store consent acknowledgment in session database

4. **API Key Management**
   - Store API key in system keyring (not files)
   - Use environment variables for configuration
   - Never commit keys to version control

5. **Error Handling**
   - Implement exponential backoff for rate limits
   - Fail entire batch on API errors (user can retry)
   - Log API failures with error details

**Implementation Pattern:**

```python
import anthropic
import os

class ClaudeEmailClassifier:
    def __init__(self, api_key=None):
        """Initialize Claude client."""
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-3-haiku-20240307"

    def classify_email(self, email_content, available_labels, subject=""):
        """
        Classify a single email using Claude API.

        Args:
            email_content: Email body text
            available_labels: List of Gmail label names to choose from
            subject: Email subject line

        Returns:
            Dict with suggested_label, confidence, reasoning
        """
        # Construct prompt
        prompt = f"""You are an email classification assistant. Given an email, suggest the most appropriate label from the provided list.

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

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            import json
            result = json.loads(response.content[0].text)

            # Validate label is in allowed list
            if result['suggested_label'] not in available_labels and result['suggested_label'] != "No Match":
                result['suggested_label'] = "No Match"
                result['reasoning'] += " (Invalid label suggested, marked as No Match)"

            return result

        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    def classify_batch(self, emails, available_labels):
        """
        Classify multiple emails in a single API call.

        Args:
            emails: List of dicts with 'subject' and 'body'
            available_labels: List of Gmail label names

        Returns:
            List of classification results
        """
        # Construct batch prompt
        email_list = "\n\n".join([
            f"Email {i+1}:\nSubject: {email['subject']}\nBody: {email['body'][:500]}"
            for i, email in enumerate(emails)
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
  {{"email_num": 1, "suggested_label": "Work", "confidence": 0.85, "reasoning": "..."}}
]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            results = json.loads(response.content[0].text)

            # Validate labels
            for result in results:
                if result['suggested_label'] not in available_labels and result['suggested_label'] != "No Match":
                    result['suggested_label'] = "No Match"

            return results

        except Exception as e:
            raise Exception(f"Claude API batch error: {str(e)}")

    def generate_summary_brief(self, no_match_emails):
        """
        Generate summary brief for unclassified emails using Claude.

        Args:
            no_match_emails: List of emails that didn't match any label

        Returns:
            Dict with grouped emails and summaries
        """
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
4. Suggested action (create_new_label/archive/delete_all)

Response format (JSON):
[
  {{
    "group_type": "sender",
    "group_key": "newsletters@company.com",
    "email_numbers": [1, 3, 5],
    "summary": "...",
    "suggested_action": "create_new_label"
  }}
]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            groups = json.loads(response.content[0].text)
            return groups

        except Exception as e:
            raise Exception(f"Claude API summary error: {str(e)}")


# Usage example
classifier = ClaudeEmailClassifier(api_key="your-api-key")

# Single email classification
result = classifier.classify_email(
    email_content="Your bank statement for January is now available to view online.",
    available_labels=["Finance", "Work", "Personal", "Shopping"],
    subject="Monthly Bank Statement"
)

print(f"Suggested Label: {result['suggested_label']}")
print(f"Confidence: {result['confidence']}")
print(f"Reasoning: {result['reasoning']}")

# Batch classification (10 emails at once)
emails = [
    {"subject": "Meeting tomorrow", "body": "Let's meet at 10am to discuss the project"},
    {"subject": "Invoice #12345", "body": "Your payment of $500 has been processed"}
]
available_labels = ["Meetings", "Finance", "Shopping", "Personal"]

batch_results = classifier.classify_batch(emails, available_labels)
for result in batch_results:
    print(f"Email {result['email_num']}: {result['suggested_label']} ({result['confidence']})")

# Generate summary for unclassified emails
no_match_emails = [
    {"sender": "news@tech.com", "subject": "Daily Newsletter", "body": "Top tech news..."},
    {"sender": "news@tech.com", "subject": "Weekly Digest", "body": "This week in tech..."}
]

summaries = classifier.generate_summary_brief(no_match_emails)
for group in summaries:
    print(f"Group: {group['group_key']}")
    print(f"Summary: {group['summary']}")
    print(f"Action: {group['suggested_action']}")
```

**Privacy & Security Considerations:**

1. **User Consent**: Display clear consent dialog explaining:
   - Full email content (subject, body, sender) sent to Anthropic API
   - Data processed in cloud, not stored by Anthropic (per their policy)
   - User can opt-out at any time

2. **API Key Storage**: Store in system keyring using `keyring` library:
```python
import keyring

# Store API key
keyring.set_password("gmail_classifier", "anthropic_api_key", api_key)

# Retrieve API key
api_key = keyring.get_password("gmail_classifier", "anthropic_api_key")
```

3. **Rate Limiting**: Claude API has rate limits:
   - Haiku: 50,000 requests per minute (more than sufficient)
   - Implement exponential backoff for 429 errors

**Testing Strategy:**

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_claude_client():
    """Mock Anthropic client for testing."""
    with patch('anthropic.Anthropic') as mock:
        client = Mock()
        mock.return_value = client

        # Mock successful response
        client.messages.create.return_value = Mock(
            content=[Mock(text='{"suggested_label": "Finance", "confidence": 0.85, "reasoning": "Bank statement email"}')]
        )

        yield client

def test_classify_email(mock_claude_client):
    """Test email classification with mocked Claude API."""
    classifier = ClaudeEmailClassifier(api_key="test-key")

    result = classifier.classify_email(
        email_content="Bank statement attached",
        available_labels=["Finance", "Work"],
        subject="Monthly Statement"
    )

    assert result['suggested_label'] == 'Finance'
    assert result['confidence'] == 0.85
    assert 'Bank statement' in result['reasoning']

def test_label_validation(mock_claude_client):
    """Test that invalid labels are caught."""
    # Mock response with invalid label
    mock_claude_client.messages.create.return_value = Mock(
        content=[Mock(text='{"suggested_label": "InvalidLabel", "confidence": 0.9, "reasoning": "test"}')]
    )

    classifier = ClaudeEmailClassifier(api_key="test-key")
    result = classifier.classify_email(
        email_content="Test email",
        available_labels=["Finance", "Work"]
    )

    # Should be converted to "No Match"
    assert result['suggested_label'] == 'No Match'
```

**Verdict:** RECOMMENDED - Best option for projects requiring high-quality semantic understanding, natural language summaries, and label constraint enforcement. API costs are minimal (<$0.20 per 1000 emails). Requires user consent for cloud processing.

---

#### Option 2: sentence-transformers (Local Alternative)

**Official Documentation:** https://scikit-learn.org/

**Advantages:**
- Lightweight and fast
- Minimal dependencies (numpy, scipy, joblib)
- Excellent documentation and tutorials
- Well-established, stable library
- Works well for keyword-based matching
- Low memory footprint
- Offline operation (no model downloads)
- Easy to understand and debug
- Good baseline for comparison

**Disadvantages:**
- Bag-of-words approach misses semantic meaning
- "cheap flight" vs "inexpensive travel" won't match well
- Poor performance on short or low-content emails
- Requires significant labeled training data
- No understanding of context or synonyms
- Struggles with paraphrasing and similar meanings

**Best For:**
- Projects with large labeled datasets
- Keyword-heavy classification tasks
- Resource-constrained environments
- Projects requiring fast inference
- When interpretability is important

**Installation:**
```bash
pip install scikit-learn
```

**Implementation Pattern:**

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, linear_kernel
import numpy as np

class EmailClassifierTFIDF:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),  # unigrams and bigrams
            min_df=2,  # ignore terms appearing in less than 2 docs
            stop_words='english',
            max_features=5000
        )
        self.labeled_vectors = None
        self.labeled_categories = None

    def fit(self, labeled_emails, categories):
        """Train on labeled email corpus."""
        self.labeled_categories = categories
        self.labeled_vectors = self.vectorizer.fit_transform(labeled_emails)

    def classify(self, unlabeled_email, top_k=3):
        """Classify an email and return top-k matches with confidence."""
        # Transform the unlabeled email
        unlabeled_vector = self.vectorizer.transform([unlabeled_email])

        # Calculate cosine similarities
        # linear_kernel is faster than cosine_similarity for TF-IDF
        similarities = linear_kernel(unlabeled_vector, self.labeled_vectors).flatten()

        # Get top-k most similar emails
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append({
                'category': self.labeled_categories[idx],
                'confidence': float(similarities[idx]),
                'index': int(idx)
            })

        return results

# Usage example
classifier = EmailClassifierTFIDF()

# Training data
labeled_emails = [
    "Meeting scheduled for tomorrow at 10am",
    "Your invoice for January is attached",
    "Reminder: Project deadline is Friday",
    "Payment received, thank you",
    "Conference call rescheduled to 3pm"
]
categories = ['meetings', 'finance', 'reminders', 'finance', 'meetings']

classifier.fit(labeled_emails, categories)

# Classify new email
new_email = "Can we move our appointment to next week?"
results = classifier.classify(new_email, top_k=3)

for result in results:
    print(f"Category: {result['category']}, Confidence: {result['confidence']:.3f}")
```

**Confidence Scoring with TF-IDF:**
- Cosine similarity ranges from 0 (no similarity) to 1 (identical)
- Scores typically fall between 0.1-0.8 for real emails
- Threshold recommendations:
  - High confidence: > 0.5
  - Medium confidence: 0.3 - 0.5
  - Low confidence: < 0.3 (flag for human review)
- Low scores on all categories indicate unclear classification

**Handling Short/Low-Content Emails:**
- TF-IDF struggles with short emails (< 50 words)
- Mitigation strategies:
  - Use subject line + body combined
  - Reduce `min_df` parameter for small datasets
  - Include metadata (sender, recipient, labels)
  - Use character n-grams in addition to word n-grams
  - Consider hybrid approach with rules for common short patterns

---

#### Option 2: sentence-transformers (RECOMMENDED)

**Official Documentation:** https://sbert.net/
**Hugging Face:** https://huggingface.co/sentence-transformers

**Advantages:**
- Semantic understanding - "cheap flight" matches "inexpensive travel"
- Pre-trained models available (no training required)
- Works well with small labeled datasets
- Excellent performance on short emails
- Captures context and meaning
- Offline operation after initial model download
- Modern, actively maintained
- State-of-the-art performance
- Easy to use with scikit-learn classifiers

**Disadvantages:**
- Larger model size (90-420 MB depending on model)
- Slower inference than TF-IDF (but still fast enough)
- Requires more memory
- Initial model download needed
- GPU helpful but not required

**Best For:**
- Projects requiring semantic understanding
- Small labeled datasets
- Short or low-content emails
- When accuracy is more important than speed
- Matching similar meanings rather than exact keywords

**Installation:**
```bash
pip install sentence-transformers
```

**Recommended Models:**

1. **all-MiniLM-L6-v2** (RECOMMENDED)
   - Size: ~90 MB
   - Embedding dimension: 384
   - Speed: Fast
   - Quality: High
   - Best balance of size, speed, and accuracy
   - Trained on 1B+ sentence pairs

2. **all-mpnet-base-v2**
   - Size: ~420 MB
   - Embedding dimension: 768
   - Speed: Medium
   - Quality: Highest
   - Best performance, but larger

3. **paraphrase-MiniLM-L6-v2**
   - Size: ~90 MB
   - Embedding dimension: 384
   - Speed: Fast
   - Quality: High
   - Good for paraphrase detection

**Implementation Pattern:**

```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class EmailClassifierSemantic:
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        """Initialize with pre-trained model."""
        # Model is downloaded on first use, cached locally
        self.model = SentenceTransformer(model_name)
        self.labeled_embeddings = None
        self.labeled_categories = None

    def save_model_locally(self, path='./models/email-classifier'):
        """Save model for offline use."""
        self.model.save(path)

    def load_model_locally(self, path='./models/email-classifier'):
        """Load model from local path."""
        self.model = SentenceTransformer(path)

    def fit(self, labeled_emails, categories):
        """Encode labeled email corpus."""
        self.labeled_categories = categories
        # Convert emails to 384-dimensional embeddings
        self.labeled_embeddings = self.model.encode(
            labeled_emails,
            convert_to_tensor=False,
            show_progress_bar=True
        )

    def classify(self, unlabeled_email, top_k=3, threshold=0.3):
        """
        Classify an email and return top-k matches with confidence.

        Args:
            unlabeled_email: Email text to classify
            top_k: Number of top matches to return
            threshold: Minimum confidence score (0.3 recommended)

        Returns:
            List of dicts with category, confidence, and index
        """
        # Encode the unlabeled email
        unlabeled_embedding = self.model.encode(
            [unlabeled_email],
            convert_to_tensor=False
        )

        # Calculate cosine similarities
        similarities = cosine_similarity(
            unlabeled_embedding,
            self.labeled_embeddings
        ).flatten()

        # Get top-k most similar emails
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            confidence = float(similarities[idx])
            if confidence >= threshold:
                results.append({
                    'category': self.labeled_categories[idx],
                    'confidence': confidence,
                    'index': int(idx),
                    'confidence_level': self._get_confidence_level(confidence)
                })

        return results

    def _get_confidence_level(self, score):
        """Classify confidence level."""
        if score >= 0.7:
            return 'high'
        elif score >= 0.5:
            return 'medium'
        else:
            return 'low'

    def classify_batch(self, unlabeled_emails, top_k=3):
        """Classify multiple emails efficiently."""
        unlabeled_embeddings = self.model.encode(
            unlabeled_emails,
            convert_to_tensor=False,
            show_progress_bar=True
        )

        results = []
        for i, embedding in enumerate(unlabeled_embeddings):
            similarities = cosine_similarity(
                [embedding],
                self.labeled_embeddings
            ).flatten()

            top_indices = np.argsort(similarities)[-top_k:][::-1]

            email_results = []
            for idx in top_indices:
                email_results.append({
                    'category': self.labeled_categories[idx],
                    'confidence': float(similarities[idx]),
                    'index': int(idx)
                })

            results.append(email_results)

        return results

# Usage example
classifier = EmailClassifierSemantic()

# Training data (can be much smaller than TF-IDF)
labeled_emails = [
    "Let's schedule a meeting for tomorrow morning",
    "Please find the invoice attached for your review",
    "Don't forget the project is due this Friday",
    "We received your payment, thanks!",
    "Our call has been moved to 3pm today"
]
categories = ['meetings', 'finance', 'reminders', 'finance', 'meetings']

print("Encoding labeled emails...")
classifier.fit(labeled_emails, categories)

# Classify new email
new_email = "Can we reschedule our appointment to next week?"
results = classifier.classify(new_email, top_k=3, threshold=0.3)

print(f"\nClassifying: '{new_email}'\n")
for result in results:
    print(f"Category: {result['category']}")
    print(f"Confidence: {result['confidence']:.3f} ({result['confidence_level']})")
    print()

# Save model for offline use
classifier.save_model_locally('./models/email-classifier')

# Later, load from disk
# classifier.load_model_locally('./models/email-classifier')
```

**Confidence Scoring with Sentence Transformers:**
- Cosine similarity ranges from -1 to 1 (usually 0-1 for similar text)
- Typical ranges for email classification:
  - High confidence: >= 0.7 (strong semantic match)
  - Medium confidence: 0.5 - 0.7 (reasonable match)
  - Low confidence: 0.3 - 0.5 (weak match, consider human review)
  - Very low: < 0.3 (likely not a match)
- Semantic models generally produce higher scores than TF-IDF for similar meanings
- More reliable for short emails

**Handling Short/Low-Content Emails:**
- Sentence transformers excel at short text
- Still produces meaningful embeddings for 5-10 word emails
- Captures semantic meaning even with minimal content
- Best practices:
  - Combine subject + body for more context
  - Use lower threshold (0.3 instead of 0.5)
  - Return top-3 matches for user review
  - Consider multiple models for very short text

**Offline Operation:**
```python
# Download and save model once
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
model.save('./models/minilm-l6-v2')

# Later, load from disk (no internet required)
model = SentenceTransformer('./models/minilm-l6-v2')
```

---

#### Option 3: spaCy

**Official Documentation:** https://spacy.io/

**Advantages:**
- Fast and production-ready
- Rich linguistic features (POS tags, entities, dependencies)
- Built-in similarity using word vectors
- Good for rule-based + ML hybrid approaches
- Excellent tokenization and preprocessing
- Can be combined with scikit-learn

**Disadvantages:**
- Requires downloading language models (~500 MB for full model)
- Similarity not as good as sentence-transformers for semantic matching
- More complex setup for classification
- Word2Vec embeddings less powerful than transformer embeddings
- Steeper learning curve

**Best For:**
- Projects needing linguistic features (entities, POS tags)
- Hybrid rule-based + ML approaches
- When preprocessing quality is critical
- Extracting structured information from emails

**Installation:**
```bash
pip install spacy
python -m spacy download en_core_web_md  # 40 MB, includes word vectors
# Or for better accuracy:
python -m spacy download en_core_web_lg  # 560 MB
```

**Implementation Pattern:**

```python
import spacy
import numpy as np

class EmailClassifierSpacy:
    def __init__(self, model='en_core_web_md'):
        """Initialize with spaCy language model."""
        self.nlp = spacy.load(model)
        self.labeled_docs = []
        self.labeled_categories = []

    def fit(self, labeled_emails, categories):
        """Process and store labeled emails."""
        self.labeled_categories = categories
        self.labeled_docs = list(self.nlp.pipe(labeled_emails))

    def classify(self, unlabeled_email, top_k=3):
        """Classify email using spaCy similarity."""
        unlabeled_doc = self.nlp(unlabeled_email)

        similarities = []
        for doc in self.labeled_docs:
            # spaCy's built-in similarity (based on word vectors)
            sim = unlabeled_doc.similarity(doc)
            similarities.append(sim)

        similarities = np.array(similarities)
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append({
                'category': self.labeled_categories[idx],
                'confidence': float(similarities[idx]),
                'index': int(idx)
            })

        return results

    def extract_features(self, email_text):
        """Extract linguistic features for rule-based logic."""
        doc = self.nlp(email_text)

        return {
            'entities': [(ent.text, ent.label_) for ent in doc.ents],
            'noun_chunks': [chunk.text for chunk in doc.noun_chunks],
            'key_verbs': [token.lemma_ for token in doc if token.pos_ == 'VERB'],
            'sentences': [sent.text for sent in doc.sents]
        }

# Usage
classifier = EmailClassifierSpacy()

labeled_emails = [
    "Meeting scheduled for tomorrow at 10am",
    "Your invoice for January is attached",
]
categories = ['meetings', 'finance']

classifier.fit(labeled_emails, categories)

new_email = "Can we move our appointment to next week?"
results = classifier.classify(new_email)

# Also extract features for rule-based logic
features = classifier.extract_features(new_email)
print(f"Entities: {features['entities']}")
print(f"Key verbs: {features['key_verbs']}")
```

**Verdict:** Good for linguistic analysis and hybrid approaches, but sentence-transformers is better for pure semantic classification.

---

### Hybrid Approach: Best of Both Worlds

For maximum flexibility, consider a hybrid approach:

```python
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class HybridEmailClassifier:
    def __init__(self):
        # Semantic understanding
        self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Keyword matching
        self.tfidf_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words='english'
        )

        self.labeled_emails = []
        self.labeled_categories = []
        self.semantic_embeddings = None
        self.tfidf_vectors = None

    def fit(self, labeled_emails, categories):
        """Train both models."""
        self.labeled_emails = labeled_emails
        self.labeled_categories = categories

        # Semantic embeddings
        self.semantic_embeddings = self.semantic_model.encode(labeled_emails)

        # TF-IDF vectors
        self.tfidf_vectors = self.tfidf_vectorizer.fit_transform(labeled_emails)

    def classify(self, unlabeled_email, semantic_weight=0.7, top_k=3):
        """
        Classify using weighted combination of semantic and keyword similarity.

        Args:
            unlabeled_email: Email to classify
            semantic_weight: Weight for semantic score (0-1), TF-IDF gets (1-weight)
            top_k: Number of results to return
        """
        # Semantic similarity
        semantic_embedding = self.semantic_model.encode([unlabeled_email])
        semantic_sims = cosine_similarity(
            semantic_embedding,
            self.semantic_embeddings
        ).flatten()

        # TF-IDF similarity
        tfidf_vector = self.tfidf_vectorizer.transform([unlabeled_email])
        tfidf_sims = cosine_similarity(
            tfidf_vector,
            self.tfidf_vectors
        ).flatten()

        # Combine scores
        combined_scores = (
            semantic_weight * semantic_sims +
            (1 - semantic_weight) * tfidf_sims
        )

        # Get top-k results
        top_indices = np.argsort(combined_scores)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            results.append({
                'category': self.labeled_categories[idx],
                'confidence': float(combined_scores[idx]),
                'semantic_score': float(semantic_sims[idx]),
                'tfidf_score': float(tfidf_sims[idx]),
                'index': int(idx)
            })

        return results

# Usage
classifier = HybridEmailClassifier()
classifier.fit(labeled_emails, categories)

# Adjust weight based on your needs:
# 0.7 = prefer semantic understanding (recommended)
# 0.5 = equal weight to both
# 0.3 = prefer keyword matching
results = classifier.classify(new_email, semantic_weight=0.7)
```

---

### Final Recommendation: anthropic SDK (Claude API with Haiku)

**Why:**
1. Best semantic understanding for email classification via state-of-the-art LLM
2. Handles both classification AND summarization with consistent approach
3. No local ML models needed - cloud-based solution
4. Natural label constraint enforcement (provide list in prompt)
5. High-quality natural language summaries for briefing
6. Works with minimal labeled data - few-shot learning
7. Easy confidence scoring via prompt engineering
8. Minimal API costs (<$0.20 per 1000 emails with Haiku)
9. Supports batch processing for efficiency
10. Automatically handles topic-based grouping and similarity detection

**Model Recommendation:** `claude-3-haiku-20240307`
- Fast inference (~200-500ms per request)
- Low cost ($0.25 per million input tokens)
- High quality semantic understanding
- 200K context window (can process multiple emails in single call)
- Reliable JSON output for structured responses

**Privacy Requirement:** User consent required before first use - full email content sent to Anthropic API for processing

**When to Use Alternatives:**
- **sentence-transformers**: If offline processing is required or cloud API is not acceptable (no user consent)
- **scikit-learn**: If you have very large labeled datasets (1000+ examples per category) and need maximum speed with no API costs
- Local alternatives sacrifice quality but provide offline operation and zero API costs

---

## Implementation Recommendations

### Project Structure

```
gmail_classifier/
├── src/
│   ├── __init__.py
│   ├── gmail_client.py           # Gmail API integration
│   ├── classifier.py              # Email classification logic
│   ├── config.py                  # Configuration management
│   └── utils.py                   # Helper functions
├── tests/
│   ├── __init__.py
│   ├── test_gmail_client.py      # Gmail API tests with mocks
│   ├── test_classifier.py        # Classifier tests
│   └── fixtures/                  # Test data
├── models/                        # Downloaded/saved models
│   └── email-classifier/
├── credentials.json               # Google Cloud credentials (git-ignored)
├── token.json                     # OAuth token (git-ignored)
├── .env                          # Environment variables (git-ignored)
├── requirements.txt
└── README.md
```

### Requirements File

```txt
# Gmail API
google-api-python-client>=2.100.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.2.0

# Email Classification & Summarization
anthropic>=0.18.0

# Credential Storage
keyring>=24.0.0

# Session State
# sqlite3 is included in Python standard library

# Testing
pytest>=7.4.0
pytest-mock>=3.12.0
pytest-cov>=4.1.0

# Utilities
python-dotenv>=1.0.0
click>=8.1.0  # For CLI
```

### Configuration Management

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Gmail API
    GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.modify']
    CREDENTIALS_PATH = 'credentials.json'
    TOKEN_PATH = 'token.json'

    # Claude API
    CLAUDE_MODEL = 'claude-3-haiku-20240307'
    CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # From environment or keyring

    # Classification
    CONFIDENCE_THRESHOLD = 0.3
    TOP_K_RESULTS = 3

    # Rate Limiting
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1  # seconds

    # Batch Processing
    BATCH_SIZE = 10  # Emails per batch

    # Privacy
    CONSENT_REQUIRED = True  # User must consent to cloud processing
```

### Error Handling Best Practices

```python
# utils.py
import time
import logging
from googleapiclient.errors import HttpError
from functools import wraps

logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries=5, initial_delay=1):
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except HttpError as error:
                    if error.resp.status == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Rate limit hit, retrying in {delay}s "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                            time.sleep(delay)
                            delay *= 2  # Exponential backoff
                        else:
                            logger.error("Max retries exceeded")
                            raise
                    else:
                        logger.error(f"HTTP error occurred: {error}")
                        raise
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    raise

            raise Exception("Max retries exceeded")
        return wrapper
    return decorator
```

---

## Testing Strategy

### Unit Tests for Gmail API

```python
# tests/test_gmail_client.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.gmail_client import GmailClient
from googleapiclient.errors import HttpError

@pytest.fixture
def mock_gmail_service():
    """Fixture providing mocked Gmail service."""
    with patch('googleapiclient.discovery.build') as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        yield mock_service

@pytest.fixture
def gmail_client(mock_gmail_service):
    """Fixture providing GmailClient with mocked service."""
    with patch('src.gmail_client.authenticate_gmail') as mock_auth:
        mock_auth.return_value = mock_gmail_service
        client = GmailClient()
        return client

def test_get_labels_success(gmail_client, mock_gmail_service):
    """Test successful label retrieval."""
    mock_gmail_service.users().labels().list().execute.return_value = {
        'labels': [
            {'id': 'INBOX', 'name': 'INBOX', 'type': 'system'},
            {'id': 'Label_1', 'name': 'Work', 'type': 'user'}
        ]
    }

    labels = gmail_client.get_labels()

    assert len(labels) == 2
    assert labels[0]['name'] == 'INBOX'
    assert labels[1]['name'] == 'Work'
    mock_gmail_service.users().labels().list.assert_called_once_with(userId='me')

def test_get_labels_http_error(gmail_client, mock_gmail_service):
    """Test error handling for label retrieval."""
    mock_gmail_service.users().labels().list().execute.side_effect = HttpError(
        resp=Mock(status=500), content=b'Internal Server Error'
    )

    labels = gmail_client.get_labels()

    assert labels == []

@pytest.mark.parametrize('status_code,should_retry', [
    (429, True),   # Rate limit - should retry
    (500, False),  # Server error - should not retry
    (404, False),  # Not found - should not retry
])
def test_retry_logic(gmail_client, mock_gmail_service, status_code, should_retry):
    """Test retry logic for different HTTP status codes."""
    mock_gmail_service.users().messages().list().execute.side_effect = HttpError(
        resp=Mock(status=status_code), content=b'Error'
    )

    with pytest.raises(HttpError):
        gmail_client.list_messages()

    if should_retry:
        # Should have been called multiple times (retries)
        assert mock_gmail_service.users().messages().list().execute.call_count > 1
    else:
        # Should fail immediately
        assert mock_gmail_service.users().messages().list().execute.call_count == 1
```

### Unit Tests for Classifier

```python
# tests/test_classifier.py
import pytest
import numpy as np
from src.classifier import EmailClassifierSemantic

@pytest.fixture
def sample_emails():
    """Sample training data."""
    return {
        'emails': [
            "Let's schedule a meeting for tomorrow",
            "Invoice attached for your review",
            "Reminder: deadline is Friday"
        ],
        'categories': ['meetings', 'finance', 'reminders']
    }

@pytest.fixture
def classifier(sample_emails):
    """Fixture providing trained classifier."""
    clf = EmailClassifierSemantic()
    clf.fit(sample_emails['emails'], sample_emails['categories'])
    return clf

def test_classifier_initialization():
    """Test classifier initializes correctly."""
    clf = EmailClassifierSemantic()
    assert clf.model is not None
    assert clf.labeled_embeddings is None

def test_classifier_fit(sample_emails):
    """Test fitting classifier with labeled data."""
    clf = EmailClassifierSemantic()
    clf.fit(sample_emails['emails'], sample_emails['categories'])

    assert clf.labeled_embeddings is not None
    assert len(clf.labeled_embeddings) == len(sample_emails['emails'])
    assert clf.labeled_embeddings.shape[1] == 384  # MiniLM dimension

def test_classifier_classify(classifier):
    """Test classification returns expected format."""
    test_email = "Can we reschedule our meeting?"
    results = classifier.classify(test_email, top_k=2)

    assert len(results) <= 2
    assert all('category' in r for r in results)
    assert all('confidence' in r for r in results)
    assert all(0 <= r['confidence'] <= 1 for r in results)

def test_classifier_semantic_understanding(classifier):
    """Test semantic understanding (synonyms)."""
    # "appointment" should match "meeting"
    test_email = "I have an appointment tomorrow"
    results = classifier.classify(test_email, top_k=1)

    assert results[0]['category'] == 'meetings'
    assert results[0]['confidence'] > 0.4

def test_classifier_short_email(classifier):
    """Test classification of short emails."""
    test_email = "meeting tomorrow?"
    results = classifier.classify(test_email, top_k=1)

    assert len(results) > 0
    assert results[0]['category'] == 'meetings'

def test_classifier_confidence_threshold(classifier):
    """Test confidence threshold filtering."""
    # Unrelated email should have low confidence
    test_email = "The weather is nice today"
    results = classifier.classify(test_email, threshold=0.5)

    # With high threshold, may return no results
    assert all(r['confidence'] >= 0.5 for r in results)

@pytest.mark.parametrize('email,expected_category', [
    ("Meeting at 3pm", 'meetings'),
    ("Bill payment due", 'finance'),
    ("Don't forget deadline", 'reminders'),
])
def test_classifier_various_inputs(classifier, email, expected_category):
    """Test classifier with various inputs."""
    results = classifier.classify(email, top_k=1)
    assert results[0]['category'] == expected_category
```

---

## Performance Considerations

### Gmail API
- **Rate Limits:** 250 quota units/user/second
- **Batch Requests:** Combine multiple calls to reduce quota usage
- **Caching:** Store message metadata locally to minimize API calls
- **Exponential Backoff:** Implement retry logic for rate limit errors

### Sentence Transformers
- **Model Size:** all-MiniLM-L6-v2 = 90MB
- **Inference Speed:** ~5-10ms per email on CPU, <1ms on GPU
- **Memory:** ~500MB RAM for model + embeddings
- **Batch Processing:** Process multiple emails at once for efficiency

### Scalability
- For 1000 emails:
  - TF-IDF: ~1-2 seconds
  - Sentence Transformers: ~5-10 seconds (CPU), ~1-2 seconds (GPU)
- Both approaches scale linearly with number of emails

---

## Summary Table

| Criterion | google-api-python-client | sentence-transformers | scikit-learn |
|-----------|-------------------------|----------------------|--------------|
| **Production Ready** | Yes | Yes | Yes |
| **Maintenance** | Official, Active | Active | Active |
| **Learning Curve** | Medium | Easy | Easy |
| **Setup Complexity** | Medium | Low | Low |
| **Semantic Understanding** | N/A | Excellent | Poor |
| **Short Email Performance** | N/A | Excellent | Poor |
| **Speed** | N/A | Fast | Fastest |
| **Memory Usage** | Low | Medium | Low |
| **Model Size** | N/A | 90MB | None |
| **Offline Operation** | Yes (after auth) | Yes (after download) | Yes |
| **Training Data Required** | N/A | None (pre-trained) | Large |
| **Best For** | Gmail API access | Semantic matching | Keyword matching |

---

## References

### Gmail API
- Official Documentation: https://developers.google.com/gmail/api
- Python Client: https://github.com/googleapis/google-api-python-client
- Usage Limits: https://developers.google.com/gmail/api/reference/quota
- Python Quickstart: https://developers.google.com/gmail/api/quickstart/python

### Sentence Transformers
- Official Docs: https://sbert.net/
- Hugging Face: https://huggingface.co/sentence-transformers
- Pre-trained Models: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- GitHub: https://github.com/UKPLab/sentence-transformers

### Scikit-learn
- Official Docs: https://scikit-learn.org/
- TfidfVectorizer: https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html
- Cosine Similarity: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html

### Testing
- pytest: https://docs.pytest.org/
- unittest.mock: https://docs.python.org/3/library/unittest.mock.html
- pytest-mock: https://pytest-mock.readthedocs.io/

### Additional Resources
- Real Python - Testing External APIs with Mocks: https://realpython.com/testing-third-party-apis-with-mocks/
- OAuth2 Best Practices: https://developers.google.com/identity/protocols/oauth2
- Email Classification Survey: https://www.tandfonline.com/doi/full/10.1080/21642583.2025.2474450

---

## Conclusion

Based on comprehensive research of current best practices, industry standards, and project requirements (including summarization and label constraint enforcement):

**For Gmail API Integration:** Use **google-api-python-client**
- Official library with modern OAuth2 support
- Production-ready with proper rate limiting and error handling
- Full API coverage and long-term support

**For Email Classification & Summarization:** Use **anthropic SDK** with **Claude 3 Haiku**
- State-of-the-art semantic understanding via LLM
- Handles both classification AND summarization with consistent AI approach
- Natural label constraint enforcement (provide label list in prompt)
- High-quality natural language summaries for briefing users
- Minimal API costs (<$0.20 per 1000 emails)
- No local ML model management - cloud-based solution
- Batch processing support for efficiency
- Requires user consent for cloud processing

**Privacy Considerations:**
- User consent dialog required before first use
- Full email content sent to Anthropic API for classification
- API key stored securely in system keyring
- No email content persistence beyond session

This combination provides a robust, maintainable, and production-ready solution for Gmail email classification with best-in-class semantic understanding, natural language summaries, and proper API integration. The cloud-based approach eliminates ML model management complexity while providing superior quality for both classification and summarization tasks.
