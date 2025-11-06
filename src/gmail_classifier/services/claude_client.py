"""Claude API client for email classification and summarization."""

import json
from datetime import datetime
from typing import List, Optional

import anthropic

from gmail_classifier.auth.claude_auth import get_claude_api_key
from gmail_classifier.lib.cache import ClassificationCache
from gmail_classifier.lib.config import claude_config, cache_config
from gmail_classifier.lib.logger import get_logger
from gmail_classifier.lib.utils import Timer, get_confidence_category, rate_limit
from gmail_classifier.models.email import Email
from gmail_classifier.models.label import Label
from gmail_classifier.models.suggestion import ClassificationSuggestion, SuggestedLabel

logger = get_logger(__name__)


class ClaudeClient:
    """Claude API client for email classification and summarization."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude API client.

        Args:
            api_key: Anthropic API key (defaults to keyring/env)

        Raises:
            ValueError: If no API key is available
        """
        self.api_key = api_key or get_claude_api_key()

        if not self.api_key:
            raise ValueError(
                "No Claude API key found. Please set up API key using:\n"
                "  python -m gmail_classifier.cli.main setup-claude\n"
                "Or set ANTHROPIC_API_KEY environment variable"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = claude_config.model
        self.cache = ClassificationCache()

        logger.info(f"Claude API client initialized with model {self.model}")

    @rate_limit(calls_per_second=claude_config.api_rate_limit)
    def classify_email(
        self,
        email: Email,
        available_labels: List[Label],
    ) -> ClassificationSuggestion:
        """
        Classify a single email using Claude API.

        Args:
            email: Email to classify
            available_labels: List of available Gmail labels

        Returns:
            ClassificationSuggestion with suggested labels and confidence

        Raises:
            Exception: If API call fails
        """
        try:
            with Timer(f"classify_email_{email.id[:8]}"):
                # Prepare label list for Claude
                label_names = [label.name for label in available_labels]

                # Try cache first
                cached = self.cache.get(
                    email.content,
                    label_names,
                    max_age_hours=cache_config.classification_max_age_hours
                )

                if cached:
                    # Update email_id (cached suggestion has old ID)
                    cached.email_id = email.id
                    logger.info(f"Cache hit for email {email.id}")
                    return cached

                # Construct classification prompt
                prompt = self._build_classification_prompt(email, label_names)

                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    temperature=0.0,  # Deterministic responses
                    messages=[{"role": "user", "content": prompt}],
                )

                # Parse response
                response_text = response.content[0].text
                classification_data = self._parse_classification_response(response_text)

                # Create suggestion object
                suggestion = self._create_suggestion_from_response(
                    email.id,
                    classification_data,
                    available_labels,
                )

                # Cache result
                self.cache.set(email.content, label_names, suggestion)
                logger.debug(f"Cached classification for email {email.id}")

                logger.info(
                    f"Classified email {email.id}: "
                    f"{suggestion.confidence_category} confidence"
                )

                return suggestion

        except Exception as e:
            logger.error(f"Failed to classify email {email.id}: {e}")
            # Return no-match suggestion on error
            return ClassificationSuggestion.create_no_match(
                email_id=email.id,
                reasoning=f"Classification failed: {str(e)}",
            )

    @rate_limit(calls_per_second=claude_config.api_rate_limit)
    def classify_batch(
        self,
        emails: List[Email],
        available_labels: List[Label],
    ) -> List[ClassificationSuggestion]:
        """
        Classify multiple emails in a single API call for efficiency.

        Args:
            emails: List of emails to classify
            available_labels: List of available Gmail labels

        Returns:
            List of ClassificationSuggestion objects
        """
        if not emails:
            return []

        try:
            with Timer(f"classify_batch_{len(emails)}_emails"):
                label_names = [label.name for label in available_labels]
                suggestions = []
                emails_to_classify = []
                email_index_map = {}

                # Check cache for each email
                for i, email in enumerate(emails):
                    cached = self.cache.get(
                        email.content,
                        label_names,
                        max_age_hours=cache_config.classification_max_age_hours
                    )

                    if cached:
                        # Update email_id (cached suggestion has old ID)
                        cached.email_id = email.id
                        suggestions.append(cached)
                        logger.debug(f"Cache hit for email {email.id}")
                    else:
                        # Track emails that need classification
                        email_index_map[len(emails_to_classify)] = i
                        emails_to_classify.append(email)

                # If all emails were cached, return early
                if not emails_to_classify:
                    logger.info(f"All {len(emails)} emails found in cache")
                    return suggestions

                # Build batch classification prompt for uncached emails
                prompt = self._build_batch_classification_prompt(emails_to_classify, label_names)

                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}],
                )

                # Parse batch response
                response_text = response.content[0].text
                batch_data = self._parse_batch_classification_response(response_text)

                # Create suggestions for newly classified emails
                for email_data in batch_data:
                    batch_index = email_data["email_index"]
                    email = emails_to_classify[batch_index]
                    suggestion = self._create_suggestion_from_response(
                        email.id,
                        email_data,
                        available_labels,
                    )
                    suggestions.append(suggestion)

                    # Cache result
                    self.cache.set(email.content, label_names, suggestion)
                    logger.debug(f"Cached classification for email {email.id}")

                logger.info(
                    f"Classified batch of {len(suggestions)} emails "
                    f"({len(emails_to_classify)} from API, {len(emails) - len(emails_to_classify)} from cache)"
                )

                return suggestions

        except Exception as e:
            logger.error(f"Failed to classify batch: {e}")
            # Return no-match suggestions for all emails
            return [
                ClassificationSuggestion.create_no_match(
                    email_id=email.id,
                    reasoning=f"Batch classification failed: {str(e)}",
                )
                for email in emails
            ]

    def _build_classification_prompt(self, email: Email, label_names: List[str]) -> str:
        """Build classification prompt for a single email."""
        return f"""You are an email classification assistant. Analyze the email below and suggest the most appropriate label(s) from the provided list.

Available labels: {', '.join(label_names)}

Email to classify:
Subject: {email.display_subject}
From: {email.display_sender}
Content: {email.content[:1000]}

Instructions:
1. Suggest up to 3 most relevant labels from the available labels list
2. Provide a confidence score (0.0-1.0) for each suggestion
3. Rank suggestions by relevance (1 = best match)
4. If no label is appropriate (confidence < 0.3), respond with no match
5. Provide brief reasoning for your classification

Respond in JSON format:
{{
  "suggested_labels": [
    {{"label_name": "label1", "confidence_score": 0.85, "rank": 1}},
    {{"label_name": "label2", "confidence_score": 0.72, "rank": 2}}
  ],
  "confidence_category": "high|medium|low|no_match",
  "reasoning": "Brief explanation"
}}

IMPORTANT: Only suggest labels from the available labels list above. Do not suggest new labels."""

    def _build_batch_classification_prompt(
        self,
        emails: List[Email],
        label_names: List[str],
    ) -> str:
        """Build classification prompt for multiple emails."""
        email_list = "\n\n".join([
            f"Email {i}:\n"
            f"Subject: {email.display_subject}\n"
            f"From: {email.display_sender}\n"
            f"Content: {email.content[:500]}"
            for i, email in enumerate(emails)
        ])

        return f"""You are an email classification assistant. Classify each email below with the most appropriate label(s).

Available labels: {', '.join(label_names)}

Emails to classify:
{email_list}

For each email, provide:
1. Up to 3 most relevant labels with confidence scores
2. Rank suggestions by relevance
3. Brief reasoning

Respond in JSON format:
[
  {{
    "email_index": 0,
    "suggested_labels": [{{"label_name": "label1", "confidence_score": 0.85, "rank": 1}}],
    "confidence_category": "high|medium|low|no_match",
    "reasoning": "Brief explanation"
  }}
]

IMPORTANT: Only suggest labels from the available labels list. Do not suggest new labels."""

    def _parse_classification_response(self, response_text: str) -> dict:
        """Parse Claude API classification response."""
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            data = json.loads(response_text)
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response: {e}")
            logger.debug(f"Response text: {response_text}")
            raise ValueError("Invalid JSON response from Claude API")

    def _parse_batch_classification_response(self, response_text: str) -> List[dict]:
        """Parse Claude API batch classification response."""
        try:
            # Extract JSON array from response
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            data = json.loads(response_text)

            if not isinstance(data, list):
                raise ValueError("Expected JSON array for batch response")

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch classification response: {e}")
            raise ValueError("Invalid JSON response from Claude API")

    def _create_suggestion_from_response(
        self,
        email_id: str,
        classification_data: dict,
        available_labels: List[Label],
    ) -> ClassificationSuggestion:
        """Create ClassificationSuggestion from parsed response data."""
        # Build label name to ID mapping
        label_map = {label.name: label.id for label in available_labels}

        # Parse suggested labels
        suggested_labels = []
        for label_data in classification_data.get("suggested_labels", []):
            label_name = label_data["label_name"]

            # Validate label exists
            if label_name not in label_map:
                logger.warning(
                    f"Claude suggested invalid label '{label_name}', "
                    "marking as no match"
                )
                continue

            suggested_labels.append(
                SuggestedLabel(
                    label_id=label_map[label_name],
                    label_name=label_name,
                    confidence_score=label_data["confidence_score"],
                    rank=label_data["rank"],
                )
            )

        # Determine confidence category
        confidence_category = classification_data.get("confidence_category", "no_match")

        # If no valid labels, treat as no match
        if not suggested_labels:
            confidence_category = "no_match"

        # Create suggestion
        return ClassificationSuggestion(
            email_id=email_id,
            suggested_labels=suggested_labels,
            confidence_category=confidence_category,
            reasoning=classification_data.get("reasoning"),
            created_at=datetime.now(),
            status="pending",
        )
