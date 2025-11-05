# Quickstart Guide: Gmail Classifier & Organizer

**Feature**: Gmail Classifier & Organizer
**Created**: 2025-11-05
**Purpose**: Get started with Gmail email classification in under 10 minutes

## Prerequisites

- Python 3.11+ installed
- Gmail account with existing labels and emails
- Google Cloud Project (free tier sufficient)
- Anthropic API key ([get one here](https://console.anthropic.com/))
- Terminal/command-line access

---

## Step 1: Python Environment Setup (2 minutes)

### Activate Virtual Environment

```bash
# Navigate to project directory
cd /path/to/gmail_classifier_speckit

# Activate .finance virtual environment
source /Users/ravivedula/Library/CloudStorage/Dropbox/1-projects/Coding/.finance/bin/activate

# Verify Python version
python --version  # Should be 3.11+
```

### Install Dependencies

```bash
# Install project dependencies using uv
uv sync --all-extras --dev

# Verify installation
python -c "import google.auth; import sentence_transformers; print('Dependencies OK')"
```

**Expected Output**: `Dependencies OK`

---

## Step 2: Gmail API Setup (5 minutes)

### 2.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project"
3. Name: "Gmail Classifier"
4. Click "Create"

### 2.2 Enable Gmail API

1. In Cloud Console, navigate to "APIs & Services" > "Library"
2. Search for "Gmail API"
3. Click "Gmail API" and click "Enable"

### 2.3 Create OAuth2 Credentials

1. Navigate to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "Gmail Classifier CLI"
5. Click "Create"
6. **Download JSON** (save as `credentials.json`)

### 2.4 Configure Credentials

```bash
# Create .env file from template
cp .env.example .env

# Edit .env file with your credentials
nano .env
```

**Add to `.env`**:
```bash
GMAIL_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GMAIL_CLIENT_SECRET="your-client-secret"
GMAIL_REDIRECT_URI="http://localhost:8080/"
```

**Important**: `.env` is gitignored for security. Never commit credentials.

---

## Step 3: Claude API Setup (2 minutes)

### 3.1 Get Anthropic API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to "API Keys"
4. Click "Create Key"
5. **Copy the API key** (you won't be able to see it again)

### 3.2 Store API Key Securely

```bash
# Run the setup command to securely store API key
python -m gmail_classifier.cli.main setup-claude

# You'll be prompted to enter your API key
# Enter API key: [paste your key here]
# API key stored securely in system keyring ✓
```

**What happens**:
- API key stored in OS system keyring (encrypted)
- Key is validated by making test API call
- Never stored in files or environment variables
- Secure retrieval for future sessions

**Troubleshooting**:
- "Invalid API key": Double-check key copied correctly from Anthropic Console
- "Keyring access denied": Check OS keyring permissions
- "API connection failed": Verify internet connection

**Privacy Note**: By setting up the API key, you consent to sending full email content (subject, body, sender) to Anthropic's Claude API for classification. Email content is processed in the cloud but not stored by Anthropic per their data policy.

---

## Step 4: First Run - Authenticate Gmail (1 minute)

### Authenticate with Gmail

```bash
# Run authentication command
python -m gmail_classifier.cli.main auth

# Expected output:
# Opening browser for Gmail authentication...
# Please authorize the application
```

**What happens**:
1. Browser opens to Google OAuth consent screen
2. Select your Gmail account
3. Click "Allow" to grant permissions
4. Browser shows "Authentication successful"
5. Refresh token stored in system keyring (secure)

**Troubleshooting**:
- If browser doesn't open: Copy URL from terminal and paste in browser
- "Access denied" error: Check OAuth client ID/secret in `.env`
- "Redirect URI mismatch": Ensure `.env` matches OAuth config

---

## Step 5: Classify Emails - Dry Run (2 minutes)

### Run Classification (No Changes)

```bash
# Classify 10 emails in dry-run mode (no labels applied)
python -m gmail_classifier.cli.main classify --dry-run --limit 10

# Expected output:
# Fetching Gmail labels... Found 5 user labels
# Fetching unlabeled emails... Found 47 unlabeled emails
# Processing first 10 emails...
#
# Email 1/10: "Your bank statement is ready"
#   Suggested: Finance (confidence: 0.92)
#   Reasoning: Email is from bank about monthly statement, clearly financial content
#
# Email 2/10: "Meeting notes from project sync"
#   Suggested: Work Projects (confidence: 0.72)
#   Reasoning: Similar to 8 emails in Work Projects label
#
# Email 3/10: "Newsletter: Daily tech news"
#   No Match (confidence: 0.21)
#   Reasoning: No similar emails found in existing labels
#
# ... (8 more emails)
#
# Summary:
# - Processed: 10 emails
# - High confidence (>0.7): 6 emails
# - Medium confidence (0.5-0.7): 2 emails
# - No match (<0.3): 2 emails
# - Dry-run mode: No changes made
```

### View Detailed Results

```bash
# Save results to file for review
python -m gmail_classifier.cli.main classify --dry-run --limit 10 --output results.json

# View JSON output
cat results.json | python -m json.tool
```

---

## Step 6: Generate Summary Brief for Unmatched Emails (1 minute)

### Create Summary for "No Match" Emails

```bash
# Generate summary brief grouped by sender
python -m gmail_classifier.cli.main summarize --group-by sender

# Expected output:
# Summary Brief: Unmatched Emails
# ================================
#
# Group 1: newsletters@techsite.com (3 emails)
#   Date Range: Oct 15 - Nov 1, 2025
#   Summary: Weekly tech newsletters covering AI, programming, and industry news.
#   Suggested Action: CREATE_NEW_LABEL ("Tech Newsletters")
#
# Group 2: notifications@social.com (5 emails)
#   Date Range: Oct 20 - Nov 3, 2025
#   Summary: Social media notifications about likes, comments, and friend requests.
#   Suggested Action: DELETE_ALL or ARCHIVE (low importance)
#
# Group 3: Various marketing senders (8 emails)
#   Date Range: Oct 10 - Nov 2, 2025
#   Summary: Promotional emails from various online retailers about sales and offers.
#   Suggested Action: CREATE_NEW_LABEL ("Marketing") or DELETE_ALL
#
# Total unmatched emails: 16
# Groups created: 3
```

---

## Step 7: Review & Apply Labels (Optional - P3 Feature)

### Interactive Review Mode

```bash
# Review suggestions before applying
python -m gmail_classifier.cli.main review

# Expected output:
# Review Classification Suggestions
# ==================================
#
# Showing 6 high-confidence suggestions:
#
# [1] "Your bank statement is ready"
#     Suggested: Finance (87%)
#     [A]pprove | [S]kip | [M]odify | [Q]uit: a
#
# [2] "Meeting notes from project sync"
#     Suggested: Work Projects (72%)
#     [A]pprove | [S]kip | [M]odify | [Q]uit: a
#
# ... (4 more)
#
# Summary: 6 approved, 0 skipped, 0 modified
# Apply labels now? [y/N]: y
#
# Applying labels...
# ✓ Applied Finance to 1 email
# ✓ Applied Work Projects to 1 email
# ... (4 more)
#
# Success: 6/6 labels applied
```

### Batch Apply (Auto-approve High Confidence)

```bash
# Auto-apply labels with confidence > 0.8
python -m gmail_classifier.cli.main apply --min-confidence 0.8

# Expected output:
# Applying labels for 4 high-confidence suggestions...
# ✓ Applied 4 labels successfully
# See log: ~/.gmail_classifier/sessions/session_2025-11-05.log
```

---

## Common Commands Reference

### Basic Usage

```bash
# Authenticate
gmail-classifier auth

# Classify emails (dry-run)
gmail-classifier classify --dry-run --limit 50

# Classify and show detailed reasoning
gmail-classifier classify --dry-run --verbose

# Generate summary brief
gmail-classifier summarize --group-by sender

# Review suggestions interactively
gmail-classifier review

# Apply labels (requires review first)
gmail-classifier apply --min-confidence 0.7
```

### Advanced Options

```bash
# Process all unlabeled emails
gmail-classifier classify --dry-run

# Resume interrupted session
gmail-classifier classify --resume session_2025-11-05

# Export results to CSV
gmail-classifier export --format csv --output results.csv

# Show processing statistics
gmail-classifier stats

# Clear old session data
gmail-classifier cleanup --older-than 30d
```

---

## Configuration Options

### ~/.gmail_classifier/config.yml

```yaml
# Classification settings
classification:
  min_confidence: 0.5
  max_suggestions: 3
  batch_size: 10  # Emails per Claude API call

# Claude API settings
claude:
  model: "claude-3-haiku-20240307"
  max_tokens: 1000
  temperature: 0.0  # Deterministic responses

# Gmail API settings
gmail:
  batch_size: 100
  rate_limit_delay: 0.5  # seconds between requests
  max_retries: 3

# Logging
logging:
  level: INFO
  file: ~/.gmail_classifier/logs/app.log

# Storage
storage:
  session_db: ~/.gmail_classifier/sessions.db
  keep_sessions_days: 30
```

---

## Troubleshooting

### "Authentication failed"
**Cause**: Invalid credentials or expired refresh token
**Fix**: Run `gmail-classifier auth` to re-authenticate

### "Rate limit exceeded"
**Cause**: Too many API requests too quickly
**Fix**: System automatically applies exponential backoff. Wait a few seconds and retry.

### "No user labels found"
**Cause**: Gmail account has no user-created labels
**Fix**: Create at least 3-5 labels in Gmail with some emails labeled. System learns from existing patterns.

### "Classification confidence very low"
**Cause**: Not enough labeled emails to learn patterns
**Fix**: Ensure each label has at least 10-15 emails labeled historically. More labeled emails = better classification.

### "Claude API error"
**Cause**: Invalid API key or network issue
**Fix**:
```bash
# Re-run Claude API setup
python -m gmail_classifier.cli.main setup-claude

# Verify API key is valid
# Test with a simple classification
```

### "API rate limit exceeded"
**Cause**: Too many Claude API requests (extremely rare with Tier 1 limits)
**Fix**: Wait a minute and retry. System automatically applies exponential backoff.

---

## Next Steps

1. **Classify More Emails**: Remove `--limit` to process all unlabeled emails
   ```bash
   gmail-classifier classify --dry-run
   ```

2. **Review & Apply**: Switch from dry-run to actual label application
   ```bash
   gmail-classifier review
   gmail-classifier apply
   ```

3. **Create Automation**: Set up cron job for periodic classification
   ```bash
   # Add to crontab: Run every Sunday at 9 AM
   0 9 * * 0 /path/to/gmail-classifier classify --apply --min-confidence 0.8
   ```

4. **Monitor Performance**: Check classification logs and statistics
   ```bash
   gmail-classifier stats --last-7-days
   ```

---

## Safety Features

### Read-Only Mode (Default)
- All commands run in dry-run mode by default
- Requires explicit `--apply` flag to modify labels
- User approval required for label application

### Session Recovery
- Progress saved every 50 emails
- Can resume interrupted sessions
- No duplicate processing

### Audit Trail
- All actions logged to `~/.gmail_classifier/logs/`
- Session history in SQLite database
- Easy rollback if needed

---

## Getting Help

### Documentation
- Full documentation: `/specs/001-gmail-classifier/`
- API reference: `gmail-classifier --help`
- Command help: `gmail-classifier <command> --help`

### Logs
- Application logs: `~/.gmail_classifier/logs/app.log`
- Session logs: `~/.gmail_classifier/sessions/`

### Debug Mode
```bash
# Enable verbose logging
gmail-classifier classify --dry-run --debug
```

---

## Security Notes

1. **Credentials Storage**: OAuth refresh token and Claude API key stored in system keyring (encrypted)
2. **No Email Persistence**: Email content never saved to disk (only metadata)
3. **API Scopes**: Minimum necessary permissions requested from Gmail
4. **Cloud Processing**: Full email content sent to Anthropic Claude API for classification (user consent required)
5. **Privacy**: Email content processed by Claude API but not stored by Anthropic per their data policy
6. **Logs**: Email content never logged (only IDs and statistics)
7. **API Key Protection**: Claude API key never logged or exposed in error messages

---

**Congratulations!** You've successfully set up and tested the Gmail Classifier. Start with dry-run mode to build confidence, then proceed to applying labels once you're comfortable with the suggestions.
