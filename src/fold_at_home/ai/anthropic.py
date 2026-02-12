"""Anthropic (Claude) AI provider."""

import json
import logging
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from .schemas import SummaryResult

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Generate summaries using Claude API."""

    def __init__(self, config):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                api_key = self.config.get_api_key()
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: "
                    "pip install fold-at-home[anthropic]"
                )
        return self._client

    def is_available(self) -> tuple[bool, str]:
        api_key = self.config.get_api_key()
        if not api_key:
            return False, "No Anthropic API key. Set anthropic_api_key in config or ANTHROPIC_API_KEY env var."
        try:
            self._get_client()
            return True, "Anthropic API ready"
        except ImportError as e:
            return False, str(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def generate_summary(self, prompt: str, system_prompt: str) -> Optional[SummaryResult]:
        client = self._get_client()
        model = self.config.model or "claude-sonnet-4-5-20250929"

        try:
            response = client.messages.create(
                model=model,
                max_tokens=2500,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                tools=[{
                    "name": "generate_summary",
                    "description": "Generate a structured protein research summary",
                    "input_schema": SummaryResult.model_json_schema(),
                }],
                tool_choice={"type": "tool", "name": "generate_summary"},
            )

            # Extract tool use result
            for block in response.content:
                if block.type == "tool_use":
                    return SummaryResult(**block.input)

            logger.warning("No tool use in Claude response")
            return None

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
