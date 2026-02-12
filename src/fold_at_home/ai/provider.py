"""AI provider protocol and factory."""

import logging
from typing import Optional, Protocol

from .schemas import SummaryResult

logger = logging.getLogger(__name__)


class AIProvider(Protocol):
    """Protocol for AI summary providers."""

    def is_available(self) -> tuple[bool, str]:
        """Check if the provider is configured and ready."""
        ...

    def generate_summary(self, prompt: str, system_prompt: str) -> Optional[SummaryResult]:
        """Generate a summary from the prompt.

        Returns SummaryResult or None on failure.
        """
        ...


def get_provider(config) -> AIProvider:
    """Factory: return the configured AI provider.

    Args:
        config: AIConfig with provider name and credentials

    Returns:
        AIProvider instance
    """
    if config.provider == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(config)
    elif config.provider == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(config)
    elif config.provider == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(config)
    else:
        raise ValueError(f"Unknown AI provider: {config.provider}")
