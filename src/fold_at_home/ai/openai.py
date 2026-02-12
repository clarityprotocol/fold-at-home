"""OpenAI (GPT-4) AI provider."""

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


class OpenAIProvider:
    """Generate summaries using OpenAI API."""

    def __init__(self, config):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import openai
                api_key = self.config.get_api_key()
                self._client = openai.OpenAI(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: "
                    "pip install fold-at-home[openai]"
                )
        return self._client

    def is_available(self) -> tuple[bool, str]:
        api_key = self.config.get_api_key()
        if not api_key:
            return False, "No OpenAI API key. Set openai_api_key in config or OPENAI_API_KEY env var."
        try:
            self._get_client()
            return True, "OpenAI API ready"
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
        model = self.config.model or "gpt-4o"

        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=2500,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "generate_summary",
                        "description": "Generate a structured protein research summary",
                        "parameters": SummaryResult.model_json_schema(),
                    },
                }],
                tool_choice={"type": "function", "function": {"name": "generate_summary"}},
            )

            message = response.choices[0].message
            if message.tool_calls:
                args = json.loads(message.tool_calls[0].function.arguments)
                return SummaryResult(**args)

            # Fallback: try parsing content as JSON
            if message.content:
                try:
                    data = json.loads(message.content)
                    return SummaryResult(**data)
                except (json.JSONDecodeError, ValueError):
                    pass

            logger.warning("No structured output from OpenAI")
            return None

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
