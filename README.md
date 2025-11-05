# Gmail Classifier & Organizer

AI-powered email classification system that analyzes unlabeled Gmail emails and suggests appropriate labels based on your existing organizational framework.

## Features

- **AI-Powered Classification**: Uses Claude 3 Haiku for semantic email understanding
- **Batch Processing**: Efficiently processes emails in configurable batches
- **Dry-Run Mode**: Preview classifications before applying changes
- **Secure Authentication**: OAuth2 with secure credential storage in system keyring
- **Session Management**: Resume interrupted classification sessions
- **Privacy-Focused**: No persistent storage of email content, only metadata
- **Read-Only by Design**: No email deletion capabilities

## Prerequisites

- Python 3.11 or higher
- Gmail account with existing labels
- Google Cloud Project with Gmail API enabled
- Anthropic API key

## Quick Start

### 1. Installation

```bash
# Clone the repository
cd gmail_classifier_speckit

# Install dependencies (using uv or pip)
pip install -e .

# Or with uv
uv sync
```

### 2. Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Gmail API
4. Create OAuth 2.0 credentials (Desktop app type)
5. Download `credentials.json` and place in project root

### 3. Authenticate

```bash
# Authenticate with Gmail
gmail-classifier auth

# Set up Claude API key
gmail-classifier setup-claude
```

### 4. Classify Emails

```bash
# Dry-run classification (no changes made)
gmail-classifier classify --limit 10 --dry-run

# Review suggestions
gmail-classifier review <session-id>

# Classify and apply labels (with confirmation)
gmail-classifier classify --apply
```

## Usage

### Authentication Commands

```bash
# Authenticate with Gmail
gmail-classifier auth

# Force re-authentication
gmail-classifier auth --force

# Set up Claude API key
gmail-classifier setup-claude

# Check authentication status
gmail-classifier status
```

### Classification Commands

```bash
# Classify emails in dry-run mode (default)
gmail-classifier classify

# Classify specific number of emails
gmail-classifier classify --limit 50

# Classify and apply labels immediately
gmail-classifier classify --apply

# Verbose output
gmail-classifier classify --verbose
```

### Review and Management

```bash
# Review classification suggestions
gmail-classifier review <session-id>

# List recent sessions
gmail-classifier sessions

# Clean up old session data
gmail-classifier cleanup --days 30
```

## Configuration

Configuration is managed through:
- Environment variables (`.env` file)
- System keyring (credentials and API keys)
- Config file at `~/.gmail_classifier/config.yml`

### Environment Variables

Create a `.env` file (see `.env.example`):

```env
# Gmail API
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret

# Application
LOG_LEVEL=INFO
BATCH_SIZE=10
CONFIDENCE_THRESHOLD=0.5
```

### Data Locations

- Session database: `~/.gmail_classifier/sessions.db`
- Logs: `~/.gmail_classifier/logs/`
- Configuration: `~/.gmail_classifier/config.yml`

## Privacy & Security

- **OAuth2 Authentication**: Secure Gmail access with read/modify permissions
- **Keyring Storage**: Credentials stored in OS-level encrypted keyring
- **No Email Persistence**: Email content never saved to disk (only IDs/metadata)
- **Cloud Processing**: Email content sent to Anthropic Claude API for classification
- **User Consent**: Explicit consent required before first use
- **PII Sanitization**: Automatic sanitization of personally identifiable information in logs

## How It Works

1. **Fetch Labels**: Retrieve user-created Gmail labels
2. **Find Unlabeled Emails**: Identify emails without user labels
3. **Batch Classification**: Send emails to Claude API in batches of 10
4. **Generate Suggestions**: Claude suggests appropriate labels with confidence scores
5. **Review & Apply**: User reviews suggestions and applies approved labels

## Classification Confidence Levels

- **High (≥0.7)**: Strong match, high confidence in classification
- **Medium (0.5-0.7)**: Reasonable match, may need review
- **Low (0.3-0.5)**: Weak match, recommend manual review
- **No Match (<0.3)**: No appropriate label found

## Example Workflow

```bash
# Step 1: Authenticate
$ gmail-classifier auth
✓ Authentication successful!

# Step 2: Set up Claude API
$ gmail-classifier setup-claude
✓ Claude API key configured successfully!

# Step 3: Run classification (dry-run)
$ gmail-classifier classify --limit 20 --dry-run
Emails processed: 20/20
Suggestions generated: 20
✓ Classification completed successfully!

# Step 4: Review suggestions
$ gmail-classifier review abc-123-def
High Confidence: 15
Medium Confidence: 3
No Match: 2

# Step 5: Apply labels (if satisfied)
$ gmail-classifier classify --apply --limit 20
```

## Development

### Project Structure

```
src/gmail_classifier/
├── auth/              # OAuth2 authentication
├── models/            # Data models (Email, Label, Session, Suggestion)
├── services/          # API clients (Gmail, Claude, Classifier)
├── cli/               # Command-line interface
└── lib/               # Utilities (config, logging, database)

tests/
├── contract/          # API contract tests
├── integration/       # End-to-end tests
└── unit/              # Component tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=gmail_classifier

# Run specific test file
pytest tests/unit/test_classifier.py
```

### Code Quality

```bash
# Format code
ruff check . --fix

# Type checking
mypy src/gmail_classifier
```

## Troubleshooting

### "No user labels found"

**Cause**: Gmail account has no user-created labels
**Solution**: Create at least 3-5 labels in Gmail with some historically labeled emails

### "Authentication failed"

**Cause**: Invalid credentials or expired token
**Solution**: Run `gmail-classifier auth --force`

### "Claude API error"

**Cause**: Invalid API key or network issue
**Solution**: Re-run `gmail-classifier setup-claude`

### "Rate limit exceeded"

**Cause**: Too many API requests
**Solution**: System automatically applies exponential backoff. Wait briefly and retry.

## Cost Estimation

Using Claude 3 Haiku:
- ~$0.0002 per email classification
- ~$0.02 per 100 emails
- ~$0.20 per 1000 emails

Very affordable for personal use!

## Limitations

- **English only**: Classification optimized for English-language emails
- **Read-only**: No email deletion capability (by design)
- **Cloud dependency**: Requires internet connection for Claude API
- **Gmail quota**: Subject to Gmail API rate limits (250 units/user/second)

## Contributing

See `ENGINEERING_STANDARDS.md` and `AGENTS.md` for development guidelines.

## License

MIT License - see LICENSE file for details

## Support

For issues or questions:
- Check documentation in `specs/001-gmail-classifier/`
- Review quickstart guide: `specs/001-gmail-classifier/quickstart.md`
- Open an issue on GitHub

## Acknowledgments

- Built with [Claude 3 Haiku](https://www.anthropic.com/) for AI classification
- Uses [Google Gmail API](https://developers.google.com/gmail/api) for email access
- CLI powered by [Click](https://click.palletsprojects.com/)
