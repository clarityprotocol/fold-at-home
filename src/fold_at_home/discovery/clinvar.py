"""ClinVar variant pathogenicity lookup via NCBI Entrez API.

Uses the same BioPython Entrez interface as PubMed — no extra dependencies
or authentication needed. ClinVar is a free, public NCBI database.
"""

import logging
from typing import Any, Dict, Optional

from Bio import Entrez
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def _parse_esummary_result(doc_summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse ClinVar esummary DocumentSummary to extract pathogenicity data."""
    try:
        germline = doc_summary.get("germline_classification", {})

        clinical_significance = germline.get("description")
        review_status = germline.get("review_status")
        last_evaluated = germline.get("last_evaluated")

        # Clean up date format ("2025/03/01 00:00" -> "2025-03-01")
        if last_evaluated and last_evaluated != "1/01/01 00:00":
            last_evaluated = last_evaluated.split()[0].replace("/", "-")
        else:
            last_evaluated = None

        if not clinical_significance:
            return None

        return {
            "clinical_significance": clinical_significance,
            "review_status": review_status,
            "last_evaluated": last_evaluated,
        }

    except Exception as e:
        logger.warning(f"Error parsing ClinVar esummary: {e}")
        return None


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=4, max=10),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _clinvar_api_call(
    gene_symbol: str, variant_notation: str, email: str, api_key: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Make ClinVar API calls with retry logic."""
    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key

    # Search: "MAPT[gene] AND P301L[variant name]"
    query = f"{gene_symbol}[gene] AND {variant_notation}[variant name]"
    logger.debug(f"ClinVar search: {query}")

    search_handle = Entrez.esearch(
        db="clinvar", term=query, retmax=1, retmode="xml"
    )
    search_result = Entrez.read(search_handle)
    search_handle.close()

    id_list = search_result.get("IdList", [])
    if not id_list:
        logger.debug(f"No ClinVar entry for {gene_symbol} {variant_notation}")
        return None

    clinvar_id = id_list[0]

    # Fetch summary (more reliable than efetch for ClinVar)
    summary_handle = Entrez.esummary(
        db="clinvar", id=clinvar_id, retmode="xml"
    )
    summary_result = Entrez.read(summary_handle, validate=False)
    summary_handle.close()

    doc_summaries = (
        summary_result.get("DocumentSummarySet", {}).get("DocumentSummary", [])
    )
    if not doc_summaries:
        return None

    return _parse_esummary_result(doc_summaries[0])


def query_clinvar(
    gene_symbol: str,
    variant_notation: str,
    email: str = "user@example.com",
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Query ClinVar for variant pathogenicity classification.

    Args:
        gene_symbol: Gene symbol (e.g., "SOD1", "MAPT", "APP")
        variant_notation: Short variant form (e.g., "A4V", "P301L")
        email: NCBI email (same as PubMed config)
        api_key: Optional NCBI API key

    Returns:
        Dict with clinical_significance, review_status, last_evaluated.
        Returns None if variant not found or API fails.
    """
    try:
        return _clinvar_api_call(gene_symbol, variant_notation, email, api_key)
    except Exception as e:
        logger.error(f"ClinVar query failed for {gene_symbol} {variant_notation}: {e}")
        return None
