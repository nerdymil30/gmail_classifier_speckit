"""Gmail Classifier CLI interface."""

import sys

import click

from gmail_classifier.auth import (
    GmailAuthenticator,
    get_claude_api_key,
    setup_claude_api_key,
    validate_claude_api_key,
)
from gmail_classifier.auth.imap import (
    IMAPAuthenticationError,
    IMAPAuthenticator,
    IMAPConnectionError,
    IMAPCredentials,
)
from gmail_classifier.lib.config import claude_config, storage_config
from gmail_classifier.lib.logger import get_logger
from gmail_classifier.lib.session_db import SessionDatabase
from gmail_classifier.services.classifier import EmailClassifier
from gmail_classifier.storage.credentials import CredentialStorage

logger = get_logger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="gmail-classifier")
def cli():
    """Gmail Classifier - AI-powered email organization tool."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Force re-authentication")
def auth(force):
    """Authenticate with Gmail API."""
    click.echo("Gmail Authentication")
    click.echo("===================")

    try:
        authenticator = GmailAuthenticator()

        if force:
            click.echo("Forcing re-authentication...")

        click.echo("Opening browser for authentication...")
        click.echo("Please authorize the application in your browser.")

        creds = authenticator.authenticate(force_reauth=force)

        if creds and creds.valid:
            click.echo("✓ Authentication successful!")
            click.echo("  Credentials saved securely in system keyring")
        else:
            click.echo("✗ Authentication failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Authentication error: {e}", err=True)
        sys.exit(1)


@cli.command()
def setup_claude():
    """Set up Anthropic Claude API key."""
    click.echo("Claude API Setup")
    click.echo("================")

    # Check if key already exists
    existing_key = get_claude_api_key()

    if existing_key:
        click.echo("An API key is already configured.")
        if not click.confirm("Do you want to replace it?"):
            click.echo("Setup cancelled.")
            return

    # Prompt for API key
    click.echo("\nGet your API key from: https://console.anthropic.com/")
    api_key = click.prompt("Enter your Anthropic API key", hide_input=True)

    if not api_key or not api_key.startswith("sk-ant-"):
        click.echo("✗ Invalid API key format", err=True)
        sys.exit(1)

    # Validate API key
    click.echo("Validating API key...")

    if not validate_claude_api_key(api_key):
        click.echo("✗ API key validation failed", err=True)
        sys.exit(1)

    # Store API key
    setup_claude_api_key(api_key)

    click.echo("✓ Claude API key configured successfully!")
    click.echo("  Key saved securely in system keyring")


@cli.command()
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of emails to classify",
)
@click.option(
    "--dry-run/--apply",
    default=True,
    help="Dry run (default) or apply labels immediately",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def classify(limit, dry_run, verbose):
    """Classify unlabeled emails."""
    click.echo("Gmail Email Classification")
    click.echo("=========================")

    if dry_run:
        click.echo("Mode: DRY RUN (no changes will be made)")
    else:
        click.echo("Mode: APPLY (labels will be applied to emails)")

        if not click.confirm("Are you sure you want to apply labels?"):
            click.echo("Classification cancelled.")
            return

    if limit:
        click.echo(f"Limit: {limit} emails")

    click.echo()

    try:
        # Create classifier
        click.echo("Initializing classifier...")
        classifier = EmailClassifier()

        # Run classification
        click.echo("Starting classification...")
        click.echo()

        session = classifier.classify_unlabeled_emails(
            max_emails=limit,
            dry_run=dry_run,
        )

        # Display results
        click.echo()
        click.echo("Classification Results")
        click.echo("=====================")
        click.echo(f"Session ID: {session.id}")
        click.echo(f"Emails processed: {session.emails_processed}/{session.total_emails_to_process}")
        click.echo(f"Suggestions generated: {session.suggestions_generated}")

        if not dry_run:
            click.echo(f"Labels applied: {session.suggestions_applied}")

        click.echo(f"Progress: {session.progress_percentage:.1f}%")
        click.echo(f"Status: {session.status}")

        if session.error_log:
            click.echo(f"\nErrors encountered: {len(session.error_log)}")

        click.echo()
        click.echo("✓ Classification completed successfully!")

        if dry_run:
            click.echo()
            click.echo("To view suggestions, run:")
            click.echo(f"  gmail-classifier review {session.id}")

    except ValueError as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Classification failed: {e}", err=True)
        logger.exception("Classification error")
        sys.exit(1)


@cli.command()
@click.argument("session_id")
def review(session_id):
    """Review classification suggestions for a session."""
    click.echo(f"Reviewing Session: {session_id}")
    click.echo("=" * (19 + len(session_id)))

    try:
        db = SessionDatabase()

        # Load session
        session = db.load_session(session_id)

        if not session:
            click.echo(f"✗ Session {session_id} not found", err=True)
            sys.exit(1)

        # Load suggestions
        suggestions = db.load_suggestions(session_id)

        if not suggestions:
            click.echo("No suggestions found for this session.")
            return

        # Display session summary
        click.echo("\nSession Summary:")
        click.echo(f"  User: {session.user_email}")
        click.echo(f"  Status: {session.status}")
        click.echo(f"  Total emails: {session.total_emails_to_process}")
        click.echo(f"  Suggestions: {len(suggestions)}")

        # Categorize suggestions
        high_conf = [s for s in suggestions if s.confidence_category == "high"]
        medium_conf = [s for s in suggestions if s.confidence_category == "medium"]
        low_conf = [s for s in suggestions if s.confidence_category == "low"]
        no_match = [s for s in suggestions if s.confidence_category == "no_match"]

        click.echo("\nConfidence Breakdown:")
        click.echo(f"  High: {len(high_conf)}")
        click.echo(f"  Medium: {len(medium_conf)}")
        click.echo(f"  Low: {len(low_conf)}")
        click.echo(f"  No Match: {len(no_match)}")

        # Show sample suggestions
        click.echo("\nSample High Confidence Suggestions:")
        click.echo("-" * 40)

        for i, suggestion in enumerate(high_conf[:5], 1):
            if suggestion.best_suggestion:
                click.echo(
                    f"{i}. Email {suggestion.email_id[:12]}... → "
                    f"{suggestion.best_suggestion.label_name} "
                    f"({suggestion.best_suggestion.confidence_score:.1%})"
                )

                if suggestion.reasoning:
                    click.echo(f"   Reason: {suggestion.reasoning[:80]}...")

        click.echo()

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def sessions():
    """List recent classification sessions."""
    click.echo("Recent Classification Sessions")
    click.echo("=============================")

    try:
        db = SessionDatabase()
        recent_sessions = db.list_sessions(limit=10)

        if not recent_sessions:
            click.echo("No sessions found.")
            return

        click.echo()

        for session in recent_sessions:
            click.echo(f"Session: {session.id}")
            click.echo(f"  User: {session.user_email}")
            click.echo(f"  Date: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"  Status: {session.status}")
            click.echo(
                f"  Progress: {session.emails_processed}/{session.total_emails_to_process} "
                f"({session.progress_percentage:.1f}%)"
            )
            click.echo(f"  Suggestions: {session.suggestions_generated}")

            if not session.is_dry_run:
                click.echo(f"  Applied: {session.suggestions_applied}")

            click.echo()

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--days",
    type=int,
    default=30,
    help="Keep sessions from last N days (default: 30)",
)
def cleanup(days):
    """Clean up old session data."""
    click.echo(f"Cleaning up sessions older than {days} days...")

    if not click.confirm("Are you sure?"):
        click.echo("Cleanup cancelled.")
        return

    try:
        db = SessionDatabase()
        deleted = db.cleanup_old_sessions(days_to_keep=days)

        click.echo(f"✓ Deleted {deleted} old sessions")

    except Exception as e:
        click.echo(f"✗ Cleanup failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def status():
    """Show authentication and configuration status."""
    click.echo("Gmail Classifier Status")
    click.echo("======================")

    # Check Gmail authentication
    authenticator = GmailAuthenticator()

    if authenticator.is_authenticated():
        click.echo("✓ Gmail: Authenticated")
    else:
        click.echo("✗ Gmail: Not authenticated")
        click.echo("  Run: gmail-classifier auth")

    # Check Claude API key
    claude_key = get_claude_api_key()

    if claude_key:
        click.echo("✓ Claude API: Configured")
    else:
        click.echo("✗ Claude API: Not configured")
        click.echo("  Run: gmail-classifier setup-claude")

    # Configuration
    click.echo()
    click.echo("Configuration:")
    click.echo(f"  Data directory: {storage_config.home_dir}")
    click.echo(f"  Session database: {storage_config.session_db_path}")
    click.echo(f"  Log directory: {storage_config.log_dir}")
    click.echo(f"  Batch size: {claude_config.batch_size} emails")
    click.echo(f"  Confidence threshold: {claude_config.confidence_threshold}")

    # Check IMAP credentials
    click.echo()
    click.echo("IMAP Authentication:")

    # Check for common Gmail accounts (user would need to specify their email)
    click.echo("  Use 'gmail-classifier login --imap' to authenticate with IMAP")
    click.echo("  Use 'gmail-classifier auth-status' to check detailed status")


@cli.command()
@click.option("--imap", is_flag=True, help="Use IMAP authentication (email + app password)")
@click.option("--email", help="Gmail email address (for IMAP)")
def login(imap, email):
    """Authenticate with Gmail (OAuth2 or IMAP).

    Examples:
        gmail-classifier login --imap --email user@gmail.com
        gmail-classifier login  # OAuth2 (default)
    """
    if imap:
        click.echo("Gmail IMAP Authentication")
        click.echo("=========================")
        click.echo()

        # Prompt for email if not provided
        if not email:
            email = click.prompt("Gmail email address")

        # Validate email format
        if "@" not in email:
            click.echo("✗ Invalid email format", err=True)
            sys.exit(1)

        click.echo()
        click.echo("IMAP Authentication requires an App Password:")
        click.echo("1. Go to: https://myaccount.google.com/apppasswords")
        click.echo("2. Sign in to your Google Account")
        click.echo("3. Generate a new app password for 'Mail'")
        click.echo("4. Copy the 16-character password")
        click.echo()

        # Prompt for app password
        password = click.prompt("Enter your App Password", hide_input=True)

        if not password or len(password) < 8:
            click.echo("✗ Invalid password format", err=True)
            sys.exit(1)

        try:
            # Create credentials
            credentials = IMAPCredentials(email=email, password=password)

            # Test authentication
            click.echo()
            click.echo("Testing IMAP connection...")

            authenticator = IMAPAuthenticator()
            session = authenticator.authenticate(credentials)

            click.echo("✓ IMAP connection successful!")

            # Store credentials securely
            storage = CredentialStorage()
            if storage.store_credentials(credentials):
                click.echo("✓ Credentials saved securely in system keyring")
                credentials.clear_password()  # Clear from memory after storage

            # Disconnect test session
            authenticator.disconnect(session.session_id)

            click.echo()
            click.echo("You can now use gmail-classifier with IMAP!")
            click.echo(f"  Authenticated as: {email}")

        except IMAPAuthenticationError as e:
            click.echo(f"✗ Authentication failed: {e}", err=True)
            click.echo()
            click.echo("Common issues:")
            click.echo("  • IMAP not enabled in Gmail settings")
            click.echo("  • Invalid app password")
            click.echo("  • 2FA not enabled (required for app passwords)")
            # Note: Password already cleared by authenticate() method on failure
            sys.exit(1)

        except IMAPConnectionError as e:
            click.echo(f"✗ Connection failed: {e}", err=True)
            click.echo()
            click.echo("Check your network connection and try again.")
            sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Error: {e}", err=True)
            # Password may have been created before error, try to clear
            try:
                if 'credentials' in locals():
                    credentials.clear_password()
            except:
                pass
            sys.exit(1)

    else:
        # Default to OAuth2 authentication (existing behavior)
        click.echo("Gmail OAuth2 Authentication")
        click.echo("===========================")
        click.echo()

        try:
            authenticator = GmailAuthenticator()
            click.echo("Opening browser for authentication...")
            click.echo("Please authorize the application in your browser.")

            creds = authenticator.authenticate(force_reauth=False)

            if creds and creds.valid:
                click.echo("✓ Authentication successful!")
                click.echo("  Credentials saved securely in system keyring")
            else:
                click.echo("✗ Authentication failed", err=True)
                sys.exit(1)

        except Exception as e:
            click.echo(f"✗ Authentication error: {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option("--email", help="Check status for specific email (IMAP)")
def auth_status(email):
    """Check authentication status for Gmail and IMAP.

    Examples:
        gmail-classifier auth-status
        gmail-classifier auth-status --email user@gmail.com
    """
    click.echo("Authentication Status")
    click.echo("====================")
    click.echo()

    # Check Gmail OAuth2
    click.echo("Gmail OAuth2:")
    try:
        authenticator = GmailAuthenticator()
        creds = authenticator.get_credentials()

        if creds and creds.valid:
            click.echo("  ✓ Authenticated")
            # Could show expiry, email, etc. if available
        else:
            click.echo("  ✗ Not authenticated")
            click.echo("    Run: gmail-classifier auth")

    except Exception as e:
        click.echo(f"  ✗ Error checking OAuth2 status: {e}")

    # Check IMAP credentials
    click.echo()
    click.echo("Gmail IMAP:")

    storage = CredentialStorage()

    if email:
        # Check specific email
        if storage.has_credentials(email):
            click.echo(f"  ✓ Credentials stored for: {email}")

            # Test connection
            click.echo("  Testing connection...")
            try:
                creds = storage.retrieve_credentials(email)
                authenticator = IMAPAuthenticator()
                session = authenticator.authenticate(creds)

                click.echo("  ✓ Connection test successful")

                # Show session info
                click.echo(f"    Session ID: {session.session_id}")
                click.echo(f"    Connected at: {session.connected_at.strftime('%Y-%m-%d %H:%M:%S')}")

                # Disconnect test session
                authenticator.disconnect(session.session_id)
                # Clear password from memory
                creds.clear_password()

            except Exception as e:
                click.echo(f"  ✗ Connection test failed: {e}")
                # Password may have been created, try to clear
                try:
                    if 'creds' in locals():
                        creds.clear_password()
                except:
                    pass

        else:
            click.echo(f"  ✗ No credentials stored for: {email}")
            click.echo(f"    Run: gmail-classifier login --imap --email {email}")

    else:
        # Show general IMAP status
        click.echo("  Use --email to check specific account")
        click.echo("  Example: gmail-classifier auth-status --email user@gmail.com")

    # Claude API status
    click.echo()
    click.echo("Claude API:")
    claude_key = get_claude_api_key()

    if claude_key:
        click.echo("  ✓ API key configured")
    else:
        click.echo("  ✗ API key not configured")
        click.echo("    Run: gmail-classifier setup-claude")


@cli.command()
@click.option("--imap", is_flag=True, help="Clear IMAP credentials")
@click.option("--email", help="Email address to logout (for IMAP)")
@click.option("--all", "logout_all", is_flag=True, help="Clear all credentials")
def logout(imap, email, logout_all):
    """Clear authentication credentials.

    Examples:
        gmail-classifier logout --imap --email user@gmail.com
        gmail-classifier logout --all  # Clear everything
    """
    click.echo("Logout")
    click.echo("======")
    click.echo()

    if logout_all:
        if not click.confirm("Clear ALL credentials (OAuth2 + IMAP)?"):
            click.echo("Logout cancelled.")
            return

        # Clear OAuth2
        try:
            authenticator = GmailAuthenticator()
            authenticator.revoke_credentials()
            click.echo("✓ OAuth2 credentials cleared")
        except Exception as e:
            click.echo(f"  Note: {e}")

        # Clear IMAP (would need to iterate all stored emails)
        if email:
            storage = CredentialStorage()
            if storage.delete_credentials(email):
                click.echo(f"✓ IMAP credentials cleared for: {email}")
            else:
                click.echo(f"  No IMAP credentials found for: {email}")

        click.echo()
        click.echo("All credentials cleared.")

    elif imap:
        if not email:
            email = click.prompt("Email address to logout")

        if not click.confirm(f"Clear IMAP credentials for {email}?"):
            click.echo("Logout cancelled.")
            return

        storage = CredentialStorage()

        if storage.delete_credentials(email):
            click.echo(f"✓ IMAP credentials cleared for: {email}")
            click.echo()
            click.echo("You will need to login again to use IMAP:")
            click.echo(f"  gmail-classifier login --imap --email {email}")
        else:
            click.echo(f"✗ No IMAP credentials found for: {email}")
            sys.exit(1)

    else:
        # Default: Clear OAuth2 only
        if not click.confirm("Clear Gmail OAuth2 credentials?"):
            click.echo("Logout cancelled.")
            return

        try:
            authenticator = GmailAuthenticator()
            authenticator.revoke_credentials()
            click.echo("✓ OAuth2 credentials cleared")
            click.echo()
            click.echo("Run 'gmail-classifier auth' to login again")

        except Exception as e:
            click.echo(f"✗ Error: {e}", err=True)
            # Password may have been created before error, try to clear
            try:
                if 'credentials' in locals():
                    credentials.clear_password()
            except:
                pass
            sys.exit(1)


if __name__ == "__main__":
    cli()
