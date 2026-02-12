"""Citation formatting for Works Cited and Similar Research sections."""

from typing import Optional


def format_works_cited_entry(
    paper: dict,
    number: int,
    relevance: Optional[str] = None,
) -> str:
    """Format a full Works Cited entry.

    Args:
        paper: Paper dict with pmid, first_author, publication_year, title, journal
        number: Citation number
        relevance: Optional 1-sentence relevance explanation

    Returns:
        Formatted citation string
    """
    author = paper.get("first_author")
    year = paper.get("publication_year")

    if author and year:
        author_year = f"{author} et al. ({year})"
    elif author:
        author_year = f"{author} et al. (n.d.)"
    elif year:
        author_year = f"Anonymous ({year})"
    else:
        author_year = f"Anonymous (PMID:{paper.get('pmid', '?')})"

    title = paper.get("title", "").strip()
    if title and not title.endswith("."):
        title += "."

    journal = paper.get("journal", "Unknown Journal").strip()
    if journal and not journal.endswith("."):
        journal += "."

    pmid = paper.get("pmid", "")
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    links = f"[PubMed]({pubmed_url})"

    doi = paper.get("doi")
    if doi:
        links += f" [DOI](https://doi.org/{doi})"

    entry = f"[{number}] {author_year}. {title} {journal} {links}"

    if relevance:
        entry += f"\n*Relevance: {relevance}*"

    return entry


def build_works_cited_section(
    papers: list[dict],
    citations_used: list[int],
    relevance_map: Optional[dict] = None,
) -> str:
    """Build complete Works Cited markdown section.

    Args:
        papers: List of paper dicts
        citations_used: Citation numbers the AI actually used
        relevance_map: Optional dict mapping citation number to relevance string

    Returns:
        Markdown Works Cited section
    """
    if not papers or not citations_used:
        return "## Works Cited\n\nNo citations."

    relevance_map = relevance_map or {}
    # Convert string keys to int if needed (from JSON parsing)
    relevance_map = {int(k): v for k, v in relevance_map.items()}

    lines = ["## Works Cited", ""]

    for i, paper in enumerate(papers, 1):
        if i in citations_used:
            relevance = relevance_map.get(i)
            entry = format_works_cited_entry(paper, i, relevance)
            lines.append(entry)
            lines.append("")

    return "\n".join(lines)


def find_similar_papers(
    papers: list[dict],
    citations_used: list[int],
    max_similar: int = 5,
) -> str:
    """Build Similar Research section from papers not cited in summary.

    Args:
        papers: All fetched papers
        citations_used: Papers already cited
        max_similar: Maximum similar papers to show

    Returns:
        Markdown Similar Research section
    """
    similar = []
    for i, paper in enumerate(papers, 1):
        if i not in citations_used:
            similar.append(paper)
        if len(similar) >= max_similar:
            break

    if not similar:
        return ""

    lines = ["## Similar Research", ""]

    for paper in similar:
        author = paper.get("first_author", "Unknown")
        year = paper.get("publication_year", "n.d.")
        title = paper.get("title", "Untitled")
        pmid = paper.get("pmid", "")

        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        lines.append(f"- {author} et al. ({year}). {title} [PubMed]({pubmed_url})")

    lines.append("")
    return "\n".join(lines)
