"""Clinical data enrichment for protein variants.

Orchestrates ClinVar and gnomAD lookups with graceful degradation.
Both are free public APIs — no authentication required.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def enrich_variant(
    gene_symbol: str,
    variant_notation: str,
    email: str = "user@example.com",
    ncbi_api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Enrich a variant with clinical data from ClinVar and gnomAD.

    Args:
        gene_symbol: Gene symbol from UniProt (e.g., "SOD1", "MAPT")
        variant_notation: Short variant form (e.g., "A4V", "P301L")
        email: NCBI email (from config, same as PubMed)
        ncbi_api_key: Optional NCBI API key (from config)

    Returns:
        Dict with clinvar and gnomad data, or None if both fail.
    """
    clinvar_data = None
    gnomad_data = None

    # ClinVar lookup
    try:
        from .clinvar import query_clinvar

        clinvar_data = query_clinvar(
            gene_symbol, variant_notation, email=email, api_key=ncbi_api_key
        )
        if clinvar_data:
            logger.info(f"ClinVar: {clinvar_data['clinical_significance']}")
    except Exception as e:
        logger.warning(f"ClinVar lookup failed: {e}")

    # gnomAD lookup
    try:
        from .gnomad import query_gnomad

        gnomad_data = query_gnomad(gene_symbol, variant_notation)
        if gnomad_data:
            logger.info(f"gnomAD AF: {gnomad_data['allele_frequency']}")
    except Exception as e:
        logger.warning(f"gnomAD lookup failed: {e}")

    if clinvar_data is None and gnomad_data is None:
        return None

    return {
        "clinvar_significance": (
            clinvar_data.get("clinical_significance") if clinvar_data else None
        ),
        "clinvar_review_status": (
            clinvar_data.get("review_status") if clinvar_data else None
        ),
        "gnomad_af": gnomad_data.get("allele_frequency") if gnomad_data else None,
        "gnomad_ac": gnomad_data.get("allele_count") if gnomad_data else None,
        "gnomad_an": gnomad_data.get("allele_number") if gnomad_data else None,
    }


def format_clinical_context(clinical_data: Optional[Dict[str, Any]]) -> str:
    """Format clinical data as text for inclusion in AI prompts.

    Returns formatted string, or empty string if no data.
    """
    if not clinical_data:
        return ""

    has_clinvar = clinical_data.get("clinvar_significance") is not None
    has_gnomad = clinical_data.get("gnomad_af") is not None

    if not has_clinvar and not has_gnomad:
        return ""

    lines = ["## Clinical Variant Data"]

    # ClinVar
    if has_clinvar:
        significance = clinical_data["clinvar_significance"]
        review = clinical_data.get("clinvar_review_status", "")
        if review:
            lines.append(f"- ClinVar Classification: {significance} ({review})")
        else:
            lines.append(f"- ClinVar Classification: {significance}")
    else:
        lines.append("- ClinVar: No entry found for this variant")

    # gnomAD
    if has_gnomad:
        af = clinical_data["gnomad_af"]
        ac = clinical_data.get("gnomad_ac")
        an = clinical_data.get("gnomad_an")

        if af is not None and af < 0.0001:
            af_str = f"{af:.2e}"
        elif af is not None:
            af_str = f"{af:.6f}"
        else:
            af_str = "N/A"

        if ac is not None and an is not None:
            lines.append(
                f"- Population Frequency (gnomAD): {af_str} "
                f"(seen in {ac}/{an} chromosomes)"
            )
        else:
            lines.append(f"- Population Frequency (gnomAD): {af_str}")
    else:
        lines.append(
            "- Population Frequency: Not observed in gnomAD "
            "(absent from general population — consistent with rare pathogenic variant)"
        )

    return "\n".join(lines)
