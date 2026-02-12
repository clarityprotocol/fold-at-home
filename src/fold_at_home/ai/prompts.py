"""Prompt templates for AI summarization.

Generalized for any protein/disease — not specific to Alzheimer's.
"""

from typing import Optional


SYSTEM_PROMPT = """You are a structural biologist writing for a general audience interested in biomedical research.

Your task is to generate:
1. A TLDR summary (2-3 sentences) that anyone can understand
2. A detailed summary with inline citations [1], [2] when papers are available

Be precise and scientifically accurate while explaining concepts in accessible language.
Define technical terms inline when first used."""


def build_summary_prompt(
    protein_name: Optional[str],
    variant: Optional[str],
    rationale: Optional[str],
    disease: Optional[str],
    uniprot_id: Optional[str],
    confidence: Optional[dict],
    rmsd: Optional[dict],
    papers: Optional[list],
) -> tuple[str, str]:
    """Build prompt and system prompt for AI summary generation.

    Args:
        protein_name: Protein name (e.g. "SOD1")
        variant: Variant notation (e.g. "A4V")
        rationale: User-provided rationale for the fold
        disease: Disease from UniProt lookup
        uniprot_id: UniProt accession
        confidence: pLDDT analysis result dict
        rmsd: RMSD comparison result dict
        papers: List of paper dicts from PubMed

    Returns:
        (prompt, system_prompt) tuple
    """
    parts = []

    # Protein context
    parts.append("## Protein Context")
    parts.append(f"- Name: {protein_name or 'Unknown'}")
    if uniprot_id:
        parts.append(f"- UniProt: {uniprot_id}")
    parts.append(f"- Variant: {variant or 'Wild-type'}")
    if disease:
        parts.append(f"- Associated Disease: {disease}")
    if rationale:
        parts.append(f"- Rationale: {rationale}")
    parts.append("")

    # Confidence analysis
    if confidence:
        parts.append("## Prediction Confidence")
        avg = confidence.get("avg_plddt", 0)
        dist = confidence.get("confidence_distribution", {})
        parts.append(f"- Average pLDDT: {avg:.1f}")
        parts.append(f"- Very high (90-100): {dist.get('very_high_90_100', 0)} residues")
        parts.append(f"- Confident (70-90): {dist.get('confident_70_90', 0)} residues")
        parts.append(f"- Low (50-70): {dist.get('low_50_70', 0)} residues")
        parts.append(f"- Very low (<50): {dist.get('very_low_0_50', 0)} residues")
        parts.append(f"- Destabilized residues: {confidence.get('num_destabilized_residues', 0)} ({confidence.get('percent_destabilized', 0):.1f}%)")

        regions = confidence.get("destabilized_regions", [])
        if regions:
            parts.append("\nDestabilized Regions:")
            for i, r in enumerate(regions, 1):
                parts.append(f"  {i}. Residues {r['start']}-{r['end']} (avg pLDDT: {r['avg_plddt']:.1f})")
        parts.append("")

    # RMSD comparison
    if rmsd:
        parts.append("## Structural Comparison to Wild-Type")
        parts.append(f"- RMSD after alignment: {rmsd.get('rmsd_after_alignment', 0):.2f} A")
        parts.append(f"- Atoms aligned: {rmsd.get('num_atoms_aligned', 0)}")
        parts.append(f"- Source: AlphaFold DB ({rmsd.get('wild_type_uniprot', '')})")
        parts.append("")

    # Literature context
    if papers:
        parts.append("## Literature References")
        parts.append("")
        parts.append("Cite relevant papers using [N] format. Track which citations you use.")
        parts.append("For each citation, provide a 1-sentence relevance explanation.")
        parts.append("")

        for i, paper in enumerate(papers[:10], 1):
            author = paper.get("first_author", "Unknown")
            year = paper.get("publication_year", "n.d.")
            title = paper.get("title", "")
            journal = paper.get("journal", "")

            parts.append(f"**[{i}]** {author} et al. ({year}). {title}. *{journal}*.")

            abstract = paper.get("abstract", "")
            if abstract:
                truncated = abstract[:400]
                if len(abstract) > 400:
                    truncated += "..."
                parts.append(f"Abstract: {truncated}")
            parts.append("")

    # Instructions
    parts.append("## Instructions")
    parts.append("")
    parts.append("Generate:")
    parts.append("1. **tldr**: 2-3 sentences for general public (no citations)")
    parts.append("2. **detailed_summary**: Full research summary with inline [N] citations")
    parts.append("3. **citations_used**: List of citation numbers you used")
    parts.append("4. **citation_relevance**: For each citation, why it's relevant")
    parts.append("")
    parts.append("**Tone:** Educated general audience")
    parts.append("**Style:** Honest about uncertainty, scientifically cautious")
    parts.append("**Formatting:** 3-5 paragraphs covering distinct aspects")

    return "\n".join(parts), SYSTEM_PROMPT
