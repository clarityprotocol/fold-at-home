"""Ollama (local LLM) AI provider.

Uses httpx directly — no extra package needed.
"""

import json
import logging
import re
from typing import Optional

import httpx

from .schemas import SummaryResult

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Generate summaries using local Ollama instance."""

    def __init__(self, config):
        self.config = config

    def is_available(self) -> tuple[bool, str]:
        try:
            response = httpx.get(
                f"{self.config.ollama_url}/api/tags",
                timeout=5.0,
            )
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                target = self.config.ollama_model
                if any(target in m for m in models):
                    return True, f"Ollama ready with {target}"
                return False, (
                    f"Model '{target}' not found. Available: {', '.join(models[:5])}\n"
                    f"Pull it with: ollama pull {target}"
                )
            return False, f"Ollama returned {response.status_code}"
        except httpx.ConnectError:
            return False, f"Cannot connect to Ollama at {self.config.ollama_url}. Is it running?"
        except Exception as e:
            return False, f"Ollama check failed: {e}"

    def generate_summary(self, prompt: str, system_prompt: str) -> Optional[SummaryResult]:
        model = self.config.ollama_model

        # Add JSON output instructions
        json_prompt = prompt + """

IMPORTANT: Respond with a JSON object containing these exact fields:
{
  "tldr": "2-3 sentence summary for general public",
  "detailed_summary": "Full research summary with [N] citations",
  "citations_used": [1, 2, 3],
  "citation_relevance": {"1": "why paper 1 is relevant", "2": "why paper 2 is relevant"}
}

Respond ONLY with valid JSON. No other text."""

        try:
            response = httpx.post(
                f"{self.config.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": json_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 2500,
                    },
                },
                timeout=300.0,  # Local models can be slow
            )

            if response.status_code != 200:
                logger.error(f"Ollama returned {response.status_code}")
                return None

            text = response.json().get("response", "")
            return self._parse_response(text)

        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.config.ollama_url}")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None

    def _parse_response(self, text: str) -> Optional[SummaryResult]:
        """Parse JSON from Ollama response, with fallback extraction."""
        # Try direct JSON parse
        try:
            data = json.loads(text)
            return SummaryResult(**data)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try extracting JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return SummaryResult(**data)
            except (json.JSONDecodeError, ValueError):
                pass

        # Try finding JSON object in text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            try:
                data = json.loads(text[brace_start : brace_end + 1])
                return SummaryResult(**data)
            except (json.JSONDecodeError, ValueError):
                pass

        # Last resort: create summary from raw text
        if len(text) > 50:
            logger.warning("Could not parse JSON from Ollama, using raw text")
            lines = text.strip().split("\n")
            tldr = lines[0] if lines else "Summary unavailable"
            detailed = text
            return SummaryResult(
                tldr=tldr,
                detailed_summary=detailed,
                citations_used=[],
                citation_relevance={},
            )

        logger.error("Ollama returned insufficient output")
        return None
