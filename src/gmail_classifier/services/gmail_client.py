"""Gmail API client wrapper with rate limiting and error handling."""

from typing import List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

from gmail_classifier.lib.cache import cached
from gmail_classifier.lib.config import gmail_config, cache_config
from gmail_classifier.lib.logger import get_logger
from gmail_classifier.lib.utils import Timer, batch_items, rate_limit, retry_with_exponential_backoff
from gmail_classifier.models.email import Email
from gmail_classifier.models.label import Label

logger = get_logger(__name__)


class GmailClient:
    """Gmail API client with rate limiting and error handling."""

    def __init__(self, credentials: Credentials):
        """
        Initialize Gmail client.

        Args:
            credentials: Valid OAuth2 credentials
        """
        self.credentials = credentials
        self.service = build("gmail", "v1", credentials=credentials)
        logger.info("Gmail API client initialized")

    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    @retry_with_exponential_backoff()
    def get_labels(self) -> List[Label]:
        """
        Fetch all Gmail labels.

        Returns:
            List of Label objects

        Raises:
            HttpError: If API request fails
        """
        try:
            with Timer("get_labels"):
                results = self.service.users().labels().list(userId="me").execute()
                labels_data = results.get("labels", [])

                labels = []
                for label_data in labels_data:
                    try:
                        label = Label.from_gmail_label(label_data)
                        labels.append(label)
                    except Exception as e:
                        logger.warning(f"Failed to parse label {label_data.get('id')}: {e}")

                logger.info(f"Retrieved {len(labels)} labels from Gmail")
                return labels

        except HttpError as error:
            logger.error(f"Failed to fetch Gmail labels: {error}")
            raise

    @cached(ttl_seconds=cache_config.label_ttl_seconds)
    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    @retry_with_exponential_backoff()
    def get_user_labels(self) -> List[Label]:
        """
        Fetch only user-created labels (excluding system labels).

        Returns:
            List of user-created Label objects
        """
        all_labels = self.get_labels()
        user_labels = [label for label in all_labels if label.is_user_label]

        logger.info(f"Found {len(user_labels)} user-created labels")
        return user_labels

    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    @retry_with_exponential_backoff()
    def list_unlabeled_messages(
        self,
        max_results: int = 100,
        page_token: Optional[str] = None,
    ) -> tuple[List[str], Optional[str]]:
        """
        List unlabeled message IDs with pagination.

        Unlabeled emails are those with only system labels (INBOX, UNREAD, etc.)
        and no user-created labels.

        Args:
            max_results: Maximum number of message IDs to return (default 100)
            page_token: Token for next page (from previous call)

        Returns:
            Tuple of (message_ids, next_page_token)
        """
        try:
            with Timer("list_unlabeled_messages"):
                # Query for messages without user labels
                # Note: We use "in:inbox" as the query, then filter unlabeled ones
                # when fetching full messages
                query = "in:inbox"

                results = (
                    self.service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        maxResults=max_results,
                        pageToken=page_token,
                    )
                    .execute()
                )

                messages = results.get("messages", [])
                message_ids = [msg["id"] for msg in messages]
                next_page_token = results.get("nextPageToken")

                logger.debug(
                    f"Listed {len(message_ids)} message IDs, "
                    f"has_more: {next_page_token is not None}"
                )

                return message_ids, next_page_token

        except HttpError as error:
            logger.error(f"Failed to list unlabeled messages: {error}")
            raise

    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    @retry_with_exponential_backoff()
    def count_unlabeled_emails(self) -> int:
        """
        Get count of unlabeled emails for progress tracking.

        Note: Gmail API doesn't provide direct count, so we use resultSizeEstimate
        which provides an approximate count.

        Returns:
            Estimated count of unlabeled emails
        """
        try:
            with Timer("count_unlabeled_emails"):
                results = (
                    self.service.users()
                    .messages()
                    .list(
                        userId="me",
                        maxResults=1,
                        q="in:inbox",
                    )
                    .execute()
                )

                count = results.get("resultSizeEstimate", 0)
                logger.debug(f"Estimated {count} unlabeled emails")
                return count

        except HttpError as error:
            logger.error(f"Failed to count unlabeled emails: {error}")
            raise

    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    @retry_with_exponential_backoff()
    def get_message(self, message_id: str) -> Email:
        """
        Fetch a single Gmail message by ID.

        Args:
            message_id: Gmail message ID

        Returns:
            Email object

        Raises:
            HttpError: If API request fails
        """
        try:
            with Timer(f"get_message_{message_id[:8]}"):
                message = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=message_id, format="full")
                    .execute()
                )

                email = Email.from_gmail_message(message)
                logger.debug(f"Retrieved message {message_id}: {email.display_subject}")
                return email

        except HttpError as error:
            logger.error(f"Failed to fetch message {message_id}: {error}")
            raise

    @rate_limit(calls_per_second=5.0)  # Lower rate for batch operations
    @retry_with_exponential_backoff()
    def get_messages_batch(self, message_ids: List[str]) -> List[Email]:
        """
        Fetch multiple messages using Gmail Batch API.

        Args:
            message_ids: List of Gmail message IDs to fetch

        Returns:
            List of Email objects

        Note:
            Gmail Batch API supports up to 100 requests per batch.
            This method automatically chunks larger requests.
        """
        with Timer("get_messages_batch"):
            emails = []
            failed_ids = []

            # Process in chunks of 100 (Gmail batch API limit)
            for chunk in batch_items(message_ids, 100):
                batch = self.service.new_batch_http_request()

                # Closure to capture results
                def callback(request_id, response, exception):
                    if exception:
                        logger.error(f"Batch request failed for message {request_id}: {exception}")
                        failed_ids.append(request_id)
                    else:
                        try:
                            email = Email.from_gmail_message(response)
                            emails.append(email)
                        except Exception as e:
                            logger.error(f"Failed to parse email {request_id}: {e}")
                            failed_ids.append(request_id)

                # Add all messages in chunk to batch
                for msg_id in chunk:
                    batch.add(
                        self.service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="full"
                        ),
                        callback=callback,
                        request_id=msg_id
                    )

                # Execute batch request
                batch.execute()

            if failed_ids:
                logger.warning(f"Failed to fetch {len(failed_ids)} messages: {failed_ids}")

            logger.info(f"Fetched {len(emails)} messages using batch API")
            return emails

    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    @retry_with_exponential_backoff()
    def modify_message_labels(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ) -> bool:
        """
        Modify labels for a message.

        Args:
            message_id: Gmail message ID
            add_labels: List of label IDs to add
            remove_labels: List of label IDs to remove

        Returns:
            True if successful

        Raises:
            HttpError: If API request fails
        """
        try:
            with Timer(f"modify_labels_{message_id[:8]}"):
                body = {}

                if add_labels:
                    body["addLabelIds"] = add_labels

                if remove_labels:
                    body["removeLabelIds"] = remove_labels

                self.service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body=body,
                ).execute()

                logger.info(
                    f"Modified labels for message {message_id}: "
                    f"added={add_labels}, removed={remove_labels}"
                )
                return True

        except HttpError as error:
            logger.error(f"Failed to modify labels for message {message_id}: {error}")
            raise

    def add_label_to_message(self, message_id: str, label_id: str) -> bool:
        """
        Add a single label to a message.

        Args:
            message_id: Gmail message ID
            label_id: Label ID to add

        Returns:
            True if successful
        """
        return self.modify_message_labels(message_id, add_labels=[label_id])

    @rate_limit(calls_per_second=gmail_config.api_rate_limit)
    def get_profile(self) -> dict:
        """
        Get the user's Gmail profile.

        Returns:
            Profile dictionary with email address
        """
        try:
            with Timer("get_profile"):
                profile = self.service.users().getProfile(userId="me").execute()
                logger.info(f"Retrieved profile for {profile.get('emailAddress')}")
                return profile

        except HttpError as error:
            logger.error(f"Failed to fetch user profile: {error}")
            raise

    def get_unlabeled_emails(
        self,
        max_results: Optional[int] = None,
    ) -> List[Email]:
        """
        Get emails that have no user-created labels.

        NOTE: This method loads all emails into memory and should be avoided
        for large email volumes. Use list_unlabeled_messages with pagination instead.

        Args:
            max_results: Maximum number of emails to retrieve

        Returns:
            List of unlabeled Email objects
        """
        # Get all message IDs using pagination
        all_message_ids = []
        page_token = None

        while True:
            # Calculate remaining slots
            remaining = None
            if max_results:
                remaining = max_results - len(all_message_ids)
                if remaining <= 0:
                    break

            # Fetch page of message IDs
            page_size = min(500, remaining) if remaining else 500
            message_ids, next_page_token = self.list_unlabeled_messages(
                max_results=page_size,
                page_token=page_token
            )

            if not message_ids:
                break

            all_message_ids.extend(message_ids)

            # Check for next page
            page_token = next_page_token
            if not page_token:
                break

            # Check if we've reached max_results
            if max_results and len(all_message_ids) >= max_results:
                all_message_ids = all_message_ids[:max_results]
                break

        if not all_message_ids:
            logger.info("No unlabeled messages found")
            return []

        # Fetch full message details
        emails = self.get_messages_batch(all_message_ids)

        # Filter to only truly unlabeled emails (no user labels)
        unlabeled_emails = [email for email in emails if email.is_unlabeled]

        logger.info(
            f"Found {len(unlabeled_emails)} unlabeled emails out of {len(emails)} retrieved"
        )

        return unlabeled_emails

    def batch_add_labels(
        self,
        email_label_pairs: List[tuple[str, str]],
    ) -> dict[str, bool]:
        """
        Add labels to multiple emails.

        Args:
            email_label_pairs: List of (email_id, label_id) tuples

        Returns:
            Dictionary mapping email_id to success status
        """
        results = {}

        for email_id, label_id in email_label_pairs:
            try:
                success = self.add_label_to_message(email_id, label_id)
                results[email_id] = success
            except Exception as e:
                logger.error(f"Failed to add label to {email_id}: {e}")
                results[email_id] = False

        success_count = sum(1 for success in results.values() if success)
        logger.info(
            f"Batch label operation: {success_count}/{len(email_label_pairs)} successful"
        )

        return results
