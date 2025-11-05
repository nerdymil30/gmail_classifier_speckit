"""Email classifier service orchestrating Gmail and Claude APIs."""

from typing import List, Optional

from gmail_classifier.auth.gmail_auth import get_gmail_credentials
from gmail_classifier.lib.config import Config
from gmail_classifier.lib.logger import get_structured_logger
from gmail_classifier.lib.session_db import SessionDatabase
from gmail_classifier.lib.utils import batch_items
from gmail_classifier.models.email import Email
from gmail_classifier.models.label import Label
from gmail_classifier.models.session import ProcessingSession
from gmail_classifier.models.suggestion import ClassificationSuggestion
from gmail_classifier.services.claude_client import ClaudeClient
from gmail_classifier.services.gmail_client import GmailClient

logger = get_structured_logger(__name__, log_file="classifier.log")


class EmailClassifier:
    """
    Orchestrates email classification workflow.

    Coordinates Gmail API for fetching emails and Claude API for classification.
    """

    def __init__(
        self,
        gmail_client: Optional[GmailClient] = None,
        claude_client: Optional[ClaudeClient] = None,
        session_db: Optional[SessionDatabase] = None,
    ):
        """
        Initialize email classifier.

        Args:
            gmail_client: Optional Gmail client (auto-authenticates if not provided)
            claude_client: Optional Claude client (uses keyring API key if not provided)
            session_db: Optional session database (uses default if not provided)
        """
        # Initialize Gmail client
        if gmail_client:
            self.gmail_client = gmail_client
        else:
            creds = get_gmail_credentials()
            self.gmail_client = GmailClient(creds)

        # Initialize Claude client
        self.claude_client = claude_client or ClaudeClient()

        # Initialize session database
        self.session_db = session_db or SessionDatabase()

        logger.info("Email classifier initialized")

    def classify_unlabeled_emails(
        self,
        max_emails: Optional[int] = None,
        dry_run: bool = True,
    ) -> ProcessingSession:
        """
        Classify unlabeled emails in user's Gmail account.

        Args:
            max_emails: Maximum number of emails to process (None = all)
            dry_run: If True, generate suggestions but don't apply labels

        Returns:
            ProcessingSession with results
        """
        logger.info(
            f"Starting classification run: "
            f"max_emails={max_emails}, dry_run={dry_run}"
        )

        # Get user profile
        profile = self.gmail_client.get_profile()
        user_email = profile.get("emailAddress", "unknown")

        # Fetch available labels
        logger.info("Fetching Gmail labels")
        user_labels = self.gmail_client.get_user_labels()

        if not user_labels:
            logger.error("No user labels found. Cannot classify without existing labels.")
            raise ValueError(
                "No user-created labels found in Gmail account. "
                "Please create at least 3-5 labels with some labeled emails first."
            )

        logger.info(f"Found {len(user_labels)} user labels: {[l.name for l in user_labels]}")

        # Fetch unlabeled emails
        logger.info("Fetching unlabeled emails")
        unlabeled_emails = self.gmail_client.get_unlabeled_emails(max_results=max_emails)

        if not unlabeled_emails:
            logger.info("No unlabeled emails found")
            return self._create_empty_session(user_email, dry_run)

        logger.info(f"Found {len(unlabeled_emails)} unlabeled emails to classify")

        # Create processing session
        session = ProcessingSession.create_new(
            user_email=user_email,
            total_emails=len(unlabeled_emails),
            config={"dry_run": dry_run, "max_emails": max_emails},
        )

        self.session_db.save_session(session)
        logger.set_context(session_id=session.id)

        # Process emails in batches
        batch_size = Config.BATCH_SIZE
        email_batches = batch_items(unlabeled_emails, batch_size)

        logger.info(f"Processing {len(unlabeled_emails)} emails in {len(email_batches)} batches")

        for batch_idx, email_batch in enumerate(email_batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(email_batches)}")

            try:
                # Classify batch
                suggestions = self.claude_client.classify_batch(email_batch, user_labels)

                # Save suggestions to database
                for suggestion in suggestions:
                    self.session_db.save_suggestion(session.id, suggestion)
                    session.increment_generated()

                    # Log classification result
                    if suggestion.best_suggestion:
                        logger.log_classification(
                            email_id=suggestion.email_id,
                            suggested_label=suggestion.best_suggestion.label_name,
                            confidence=suggestion.best_suggestion.confidence_score,
                            reasoning=suggestion.reasoning,
                        )
                    else:
                        logger.log_classification(
                            email_id=suggestion.email_id,
                            suggested_label="No Match",
                            confidence=0.0,
                            reasoning=suggestion.reasoning,
                        )

                # Update session progress
                session.emails_processed += len(email_batch)

                # Auto-save session every N emails
                if session.emails_processed % Config.AUTO_SAVE_FREQUENCY == 0:
                    self.session_db.save_session(session)
                    logger.log_session_progress(
                        session_id=session.id,
                        processed=session.emails_processed,
                        total=session.total_emails_to_process,
                    )

            except Exception as e:
                error_msg = f"Batch {batch_idx} classification failed: {e}"
                logger.error(error_msg)
                session.add_error(error_msg)

                # For now, continue with remaining batches
                # In future, could add option to fail entire session

        # Mark session as completed
        session.complete()
        self.session_db.save_session(session)

        logger.info(
            f"Classification run completed: "
            f"{session.emails_processed}/{session.total_emails_to_process} processed, "
            f"{session.suggestions_generated} suggestions generated"
        )

        return session

    def apply_suggestions(
        self,
        session_id: str,
        min_confidence: Optional[float] = None,
        auto_approve_high_confidence: bool = False,
    ) -> dict:
        """
        Apply classification suggestions to Gmail.

        Args:
            session_id: Session ID containing suggestions
            min_confidence: Minimum confidence threshold to apply
            auto_approve_high_confidence: Auto-approve high confidence suggestions

        Returns:
            Dictionary with application results
        """
        logger.info(f"Applying suggestions for session {session_id}")

        # Load session
        session = self.session_db.load_session(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.is_dry_run:
            raise ValueError("Cannot apply suggestions from dry-run session")

        # Load pending suggestions
        suggestions = self.session_db.load_suggestions(session_id, status="pending")

        if not suggestions:
            logger.info("No pending suggestions to apply")
            return {"applied": 0, "skipped": 0, "failed": 0}

        # Filter by confidence if specified
        min_conf = min_confidence or Config.CONFIDENCE_THRESHOLD

        applicable_suggestions = [
            s
            for s in suggestions
            if s.best_suggestion and s.best_suggestion.confidence_score >= min_conf
        ]

        logger.info(
            f"Found {len(applicable_suggestions)}/{len(suggestions)} suggestions "
            f"meeting confidence threshold {min_conf}"
        )

        # Apply labels
        applied = 0
        skipped = 0
        failed = 0

        for suggestion in applicable_suggestions:
            if not suggestion.best_suggestion:
                skipped += 1
                continue

            try:
                # Apply label to email
                success = self.gmail_client.add_label_to_message(
                    suggestion.email_id,
                    suggestion.best_suggestion.label_id,
                )

                if success:
                    # Update suggestion status
                    suggestion.mark_applied()
                    self.session_db.update_suggestion_status(
                        session_id,
                        suggestion.email_id,
                        "applied",
                    )

                    session.increment_applied()
                    applied += 1

                    logger.info(
                        f"Applied label '{suggestion.best_suggestion.label_name}' "
                        f"to email {suggestion.email_id}"
                    )
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to apply label to {suggestion.email_id}: {e}")
                failed += 1

        # Save updated session
        self.session_db.save_session(session)

        results = {
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "total": len(applicable_suggestions),
        }

        logger.info(f"Label application completed: {results}")

        return results

    def get_session_summary(self, session_id: str) -> dict:
        """
        Get summary of classification session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with session summary
        """
        session = self.session_db.load_session(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found")

        suggestions = self.session_db.load_suggestions(session_id)

        # Categorize suggestions by confidence
        high_confidence = [s for s in suggestions if s.is_high_confidence]
        no_match = [s for s in suggestions if s.is_no_match]

        return {
            "session_id": session.id,
            "user_email": session.user_email,
            "status": session.status,
            "total_emails": session.total_emails_to_process,
            "emails_processed": session.emails_processed,
            "suggestions_generated": session.suggestions_generated,
            "suggestions_applied": session.suggestions_applied,
            "high_confidence_count": len(high_confidence),
            "no_match_count": len(no_match),
            "progress_percentage": session.progress_percentage,
            "success_rate": session.success_rate,
            "duration_seconds": session.duration_seconds,
            "dry_run": session.is_dry_run,
        }

    def _create_empty_session(self, user_email: str, dry_run: bool) -> ProcessingSession:
        """Create and save an empty completed session."""
        session = ProcessingSession.create_new(
            user_email=user_email,
            total_emails=0,
            config={"dry_run": dry_run},
        )

        session.complete()
        self.session_db.save_session(session)

        return session
