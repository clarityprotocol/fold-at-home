"""Pydantic schemas for AI-generated protein summaries."""

from pydantic import BaseModel, Field


class SummaryResult(BaseModel):
    """Structured output from AI summary generation.

    Used with structured outputs (Claude, GPT-4) or parsed from Ollama text.
    """

    tldr: str = Field(
        description="2-3 sentence summary for general public: what protein is, why it matters, key finding"
    )

    detailed_summary: str = Field(
        description="Full research summary with inline citations [1], [2]. "
        "Covers methods, findings, disease relevance, confidence assessment."
    )

    citations_used: list[int] = Field(
        default=[],
        description="List of citation numbers used in detailed_summary, e.g. [1, 2, 3]"
    )

    citation_relevance: dict[int, str] = Field(
        default={},
        description="For each citation used, a 1-sentence explanation of why it's relevant"
    )
