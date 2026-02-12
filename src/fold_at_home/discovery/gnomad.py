"""gnomAD population allele frequency lookup via GraphQL API.

gnomAD (Genome Aggregation Database) is a free public resource — no
authentication, no API key, no account needed. Provides population-level
allele frequencies to help interpret variant significance.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

# Amino acid 1-letter to 3-letter mapping for HGVS conversion
AA_MAP_1TO3 = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys",
    "Q": "Gln", "E": "Glu", "G": "Gly", "H": "His", "I": "Ile",
    "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro",
    "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val",
}

GENE_VARIANTS_QUERY = """
query GeneVariants($geneSymbol: String!) {
  gene(gene_symbol: $geneSymbol, reference_genome: GRCh38) {
    variants(dataset: gnomad_r4) {
      variant_id
      pos
      exome {
        af
        ac
        an
      }
      transcript_consequence {
        gene_symbol
        hgvsp
      }
    }
  }
}
"""


def _normalize_to_hgvsp(variant: str) -> List[str]:
    """Convert short variant notation (P301L) to gnomAD hgvsp formats."""
    match = re.match(r"^([A-Z])(\d+)([A-Z])$", variant.upper())
    if not match:
        return []

    orig_aa, position, new_aa = match.groups()
    orig_3 = AA_MAP_1TO3.get(orig_aa)
    new_3 = AA_MAP_1TO3.get(new_aa)

    if not orig_3 or not new_3:
        return []

    return [
        f"p.{orig_3}{position}{new_3}",  # p.Pro301Leu
        f"p.{orig_aa}{position}{new_aa}",  # p.P301L
    ]


@retry(
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
    ),
    wait=wait_exponential(multiplier=2, min=4, max=10),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _gnomad_api_call(gene_symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch all variants for a gene from gnomAD with retry logic."""
    logger.info(f"Querying gnomAD for gene {gene_symbol}")

    response = httpx.post(
        GNOMAD_API_URL,
        json={"query": GENE_VARIANTS_QUERY, "variables": {"geneSymbol": gene_symbol}},
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        logger.error(f"gnomAD GraphQL errors: {data['errors']}")
        return None

    return data


def query_gnomad(
    gene_symbol: str, variant_notation: str
) -> Optional[Dict[str, Any]]:
    """Query gnomAD for population allele frequency of a variant.

    Args:
        gene_symbol: Gene symbol (e.g., "SOD1", "MAPT")
        variant_notation: Short variant form (e.g., "A4V", "P301L")

    Returns:
        Dict with allele_frequency, allele_count, allele_number.
        Returns None if variant not found (common for rare pathogenic variants).
    """
    hgvsp_patterns = _normalize_to_hgvsp(variant_notation)
    if not hgvsp_patterns:
        logger.warning(f"Could not normalize variant {variant_notation}")
        return None

    try:
        data = _gnomad_api_call(gene_symbol)
    except Exception as e:
        logger.error(f"gnomAD query failed for {gene_symbol}: {e}")
        return None

    if not data:
        return None

    gene_data = data.get("data", {}).get("gene")
    if not gene_data:
        logger.info(f"Gene {gene_symbol} not found in gnomAD")
        return None

    variants = gene_data.get("variants", [])

    for variant in variants:
        consequences = variant.get("transcript_consequences", [])
        # gnomAD uses singular "transcript_consequence" in some schema versions
        if not consequences:
            consequence = variant.get("transcript_consequence")
            if consequence:
                consequences = [consequence] if isinstance(consequence, dict) else consequence

        for consequence in (consequences or []):
            hgvsp = consequence.get("hgvsp")
            if not hgvsp:
                continue

            for pattern in hgvsp_patterns:
                if hgvsp.endswith(pattern) or pattern in hgvsp:
                    exome = variant.get("exome")
                    if exome:
                        return {
                            "allele_frequency": exome.get("af"),
                            "allele_count": exome.get("ac"),
                            "allele_number": exome.get("an"),
                        }

    logger.info(f"Variant {variant_notation} not found in gnomAD for {gene_symbol}")
    return None
