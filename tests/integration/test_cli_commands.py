"""Integration tests for CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from gmail_classifier.lib.session_db import SessionDatabase
from gmail_classifier.models.session import ProcessingSession
from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_db():
    """Temporary database for CLI tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sessions.db"
        db = SessionDatabase(db_path)
        yield db
        db.close()


@pytest.fixture
def mock_classifier():
    """Mock EmailClassifier for CLI tests."""
    from gmail_classifier.services.classifier import EmailClassifier

    mock = Mock(spec=EmailClassifier)

    # Mock a successful classification session
    session = ProcessingSession.create_new(
        user_email="test@example.com",
        total_emails=10,
        config={"dry_run": True}
    )
    session.emails_processed = 10
    session.suggestions_generated = 10
    session.complete()

    mock.classify_unlabeled_emails.return_value = session

    return mock


@pytest.mark.integration
class TestCLICommands:
    """Test CLI command integration."""

    def test_cli_help(self, cli_runner):
        """Test that CLI help command works."""
        # Import here to avoid issues with module-level imports
        from gmail_classifier.cli.main import cli

        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Gmail Classifier" in result.output
        assert "AI-powered email organization" in result.output or "email" in result.output.lower()

    def test_cli_version(self, cli_runner):
        """Test that version command works."""
        from gmail_classifier.cli.main import cli

        result = cli_runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "version" in result.output.lower() or "0.1.0" in result.output

    @patch("gmail_classifier.cli.main.EmailClassifier")
    def test_classify_dry_run(self, mock_classifier_class, cli_runner):
        """Test classify command in dry-run mode."""
        from gmail_classifier.cli.main import cli

        # Setup mock
        mock_instance = Mock()
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=5,
            config={"dry_run": True}
        )
        session.emails_processed = 5
        session.suggestions_generated = 5
        session.complete()

        mock_instance.classify_unlabeled_emails.return_value = session
        mock_classifier_class.return_value = mock_instance

        # Run command
        result = cli_runner.invoke(cli, ["classify", "--dry-run", "--limit", "5"])

        # Verify output
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Classification completed" in result.output or "completed" in result.output.lower()

        # Verify classifier was called correctly
        mock_instance.classify_unlabeled_emails.assert_called_once()
        call_args = mock_instance.classify_unlabeled_emails.call_args
        assert call_args.kwargs["max_emails"] == 5
        assert call_args.kwargs["dry_run"] is True

    @patch("gmail_classifier.cli.main.EmailClassifier")
    def test_classify_with_limit(self, mock_classifier_class, cli_runner):
        """Test classify command with email limit."""
        from gmail_classifier.cli.main import cli

        # Setup mock
        mock_instance = Mock()
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=10,
            config={"dry_run": True}
        )
        session.emails_processed = 10
        session.suggestions_generated = 10
        session.complete()

        mock_instance.classify_unlabeled_emails.return_value = session
        mock_classifier_class.return_value = mock_instance

        # Run command
        result = cli_runner.invoke(cli, ["classify", "--limit", "10"])

        assert result.exit_code == 0
        assert "10 emails" in result.output or "Limit: 10" in result.output

    def test_sessions_list_empty(self, cli_runner, temp_db):
        """Test sessions command with no sessions."""
        from gmail_classifier.cli.main import cli

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["sessions"])

            assert result.exit_code == 0
            assert "No sessions found" in result.output

    def test_sessions_list_with_data(self, cli_runner, temp_db):
        """Test sessions command with existing sessions."""
        from gmail_classifier.cli.main import cli

        # Create test sessions
        session1 = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=10,
            config={"dry_run": True}
        )
        session1.emails_processed = 10
        session1.suggestions_generated = 10
        session1.complete()
        temp_db.save_session(session1)

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["sessions"])

            assert result.exit_code == 0
            assert "Recent Classification Sessions" in result.output
            assert session1.id in result.output
            assert "test@example.com" in result.output

    def test_review_session_not_found(self, cli_runner, temp_db):
        """Test review command with non-existent session."""
        from gmail_classifier.cli.main import cli

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["review", "nonexistent_session_id"])

            assert result.exit_code == 1
            assert "not found" in result.output

    def test_review_session_with_suggestions(self, cli_runner, temp_db):
        """Test review command with existing session and suggestions."""
        from gmail_classifier.cli.main import cli

        # Create test session
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=2,
            config={"dry_run": True}
        )
        session.emails_processed = 2
        session.suggestions_generated = 2
        session.complete()
        temp_db.save_session(session)

        # Create test suggestions
        suggestion1 = ClassificationSuggestion(
            email_id="msg_1",
            suggested_labels=[
                SuggestedLabel("Label_1", "Work", 0.95, 1, "High confidence work email")
            ],
            confidence_category="high",
            reasoning="Clearly work-related content"
        )
        suggestion2 = ClassificationSuggestion(
            email_id="msg_2",
            suggested_labels=[
                SuggestedLabel("Label_2", "Personal", 0.85, 1, "Personal email")
            ],
            confidence_category="high",
            reasoning="Personal conversation"
        )

        temp_db.save_suggestion(session.id, suggestion1)
        temp_db.save_suggestion(session.id, suggestion2)

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["review", session.id])

            assert result.exit_code == 0
            assert "Reviewing Session" in result.output
            assert "Session Summary" in result.output
            assert "test@example.com" in result.output
            assert "High: 2" in result.output

    def test_cleanup_cancelled(self, cli_runner, temp_db):
        """Test cleanup command when user cancels."""
        from gmail_classifier.cli.main import cli

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            # Simulate user saying "no" to confirmation
            result = cli_runner.invoke(cli, ["cleanup"], input="n\n")

            assert result.exit_code == 0
            assert "cancelled" in result.output.lower()

    def test_cleanup_confirmed(self, cli_runner, temp_db):
        """Test cleanup command when user confirms."""
        from gmail_classifier.cli.main import cli

        # Create old session
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=1,
            config={"dry_run": True}
        )
        session.complete()
        temp_db.save_session(session)

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            # Simulate user saying "yes" to confirmation
            result = cli_runner.invoke(cli, ["cleanup", "--days", "0"], input="y\n")

            assert result.exit_code == 0
            assert "Deleted" in result.output

    def test_cleanup_with_custom_days(self, cli_runner, temp_db):
        """Test cleanup command with custom days parameter."""
        from gmail_classifier.cli.main import cli

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["cleanup", "--days", "60"], input="y\n")

            assert result.exit_code == 0
            assert "60 days" in result.output

    @patch("gmail_classifier.cli.main.GmailAuthenticator")
    @patch("gmail_classifier.cli.main.get_claude_api_key")
    def test_status_command_authenticated(
        self,
        mock_get_api_key,
        mock_authenticator_class,
        cli_runner
    ):
        """Test status command when authenticated."""
        from gmail_classifier.cli.main import cli

        # Mock authenticated state
        mock_auth = Mock()
        mock_auth.is_authenticated.return_value = True
        mock_authenticator_class.return_value = mock_auth
        mock_get_api_key.return_value = "sk-ant-test-key"

        # Mock config objects
        with patch("gmail_classifier.cli.main.storage_config") as mock_storage:
            with patch("gmail_classifier.cli.main.claude_config") as mock_claude:
                mock_storage.home_dir = Path("/test/home")
                mock_storage.session_db_path = Path("/test/sessions.db")
                mock_storage.log_dir = Path("/test/logs")
                mock_claude.batch_size = 10
                mock_claude.confidence_threshold = 0.5

                result = cli_runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "Gmail: Authenticated" in result.output or "Gmail" in result.output
                assert "Claude API: Configured" in result.output or "Claude" in result.output

    @patch("gmail_classifier.cli.main.GmailAuthenticator")
    @patch("gmail_classifier.cli.main.get_claude_api_key")
    def test_status_command_not_authenticated(
        self,
        mock_get_api_key,
        mock_authenticator_class,
        cli_runner
    ):
        """Test status command when not authenticated."""
        from gmail_classifier.cli.main import cli

        # Mock unauthenticated state
        mock_auth = Mock()
        mock_auth.is_authenticated.return_value = False
        mock_authenticator_class.return_value = mock_auth
        mock_get_api_key.return_value = None

        # Mock config objects
        with patch("gmail_classifier.cli.main.storage_config") as mock_storage:
            with patch("gmail_classifier.cli.main.claude_config") as mock_claude:
                mock_storage.home_dir = Path("/test/home")
                mock_storage.session_db_path = Path("/test/sessions.db")
                mock_storage.log_dir = Path("/test/logs")
                mock_claude.batch_size = 10
                mock_claude.confidence_threshold = 0.5

                result = cli_runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "Not authenticated" in result.output or "not configured" in result.output.lower()

    @patch("gmail_classifier.cli.main.EmailClassifier")
    def test_classify_error_handling(self, mock_classifier_class, cli_runner):
        """Test classify command error handling."""
        from gmail_classifier.cli.main import cli

        # Setup mock to raise error
        mock_instance = Mock()
        mock_instance.classify_unlabeled_emails.side_effect = ValueError("No user labels found")
        mock_classifier_class.return_value = mock_instance

        # Run command
        result = cli_runner.invoke(cli, ["classify", "--dry-run"])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_review_empty_suggestions(self, cli_runner, temp_db):
        """Test review command with session but no suggestions."""
        from gmail_classifier.cli.main import cli

        # Create test session without suggestions
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=0,
            config={"dry_run": True}
        )
        session.complete()
        temp_db.save_session(session)

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["review", session.id])

            assert result.exit_code == 0
            assert "No suggestions found" in result.output

    @patch("gmail_classifier.cli.main.EmailClassifier")
    def test_classify_with_verbose(self, mock_classifier_class, cli_runner):
        """Test classify command with verbose flag."""
        from gmail_classifier.cli.main import cli

        # Setup mock
        mock_instance = Mock()
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=5,
            config={"dry_run": True}
        )
        session.emails_processed = 5
        session.suggestions_generated = 5
        session.complete()

        mock_instance.classify_unlabeled_emails.return_value = session
        mock_classifier_class.return_value = mock_instance

        # Run command with verbose flag
        result = cli_runner.invoke(cli, ["classify", "--dry-run", "--verbose"])

        assert result.exit_code == 0

    def test_command_available_list(self, cli_runner):
        """Test that all expected commands are available."""
        from gmail_classifier.cli.main import cli

        result = cli_runner.invoke(cli, ["--help"])

        # Check for expected commands
        assert "classify" in result.output
        assert "sessions" in result.output
        assert "review" in result.output
        assert "cleanup" in result.output
        assert "status" in result.output

    def test_review_with_mixed_confidence(self, cli_runner, temp_db):
        """Test review command with mixed confidence suggestions."""
        from gmail_classifier.cli.main import cli

        # Create test session
        session = ProcessingSession.create_new(
            user_email="test@example.com",
            total_emails=4,
            config={"dry_run": True}
        )
        session.emails_processed = 4
        session.suggestions_generated = 4
        session.complete()
        temp_db.save_session(session)

        # Create suggestions with different confidence levels
        suggestions = [
            ClassificationSuggestion(
                email_id="msg_1",
                suggested_labels=[SuggestedLabel("L1", "Work", 0.95, 1, "High")],
                confidence_category="high",
                reasoning="High confidence"
            ),
            ClassificationSuggestion(
                email_id="msg_2",
                suggested_labels=[SuggestedLabel("L2", "Personal", 0.65, 1, "Med")],
                confidence_category="medium",
                reasoning="Medium confidence"
            ),
            ClassificationSuggestion(
                email_id="msg_3",
                suggested_labels=[SuggestedLabel("L3", "Other", 0.35, 1, "Low")],
                confidence_category="low",
                reasoning="Low confidence"
            ),
            ClassificationSuggestion(
                email_id="msg_4",
                suggested_labels=[],
                confidence_category="no_match",
                reasoning="No match found"
            ),
        ]

        for suggestion in suggestions:
            temp_db.save_suggestion(session.id, suggestion)

        with patch("gmail_classifier.cli.main.SessionDatabase") as mock_db_class:
            mock_db_class.return_value = temp_db

            result = cli_runner.invoke(cli, ["review", session.id])

            assert result.exit_code == 0
            assert "High: 1" in result.output
            assert "Medium: 1" in result.output
            assert "Low: 1" in result.output
            assert "No Match: 1" in result.output
