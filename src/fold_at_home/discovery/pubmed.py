"""PubMed literature search for protein variant papers."""

import logging
from typing import Dict, List, Optional

from Bio import Entrez, Medline

logger = logging.getLogger(__name__)


def _parse_first_author(authors: List[str]) -> Optional[str]:
    """Extract first author surname from PubMed author list."""
    if not authors:
        return None
    return authors[0].split()[0] if authors[0].strip() else None


def _parse_year(pub_date: str) -> Optional[int]:
    """Extract year from PubMed date string."""
    if not pub_date:
        return None
    try:
        return int(pub_date.split()[0])
    except (ValueError, IndexError):
        return None


def search_papers(
    query: str,
    email: str = "user@example.com",
    api_key: Optional[str] = None,
    max_results: int = 20,
    year_range: str = "2020:2026",
) -> List[Dict]:
    """Search PubMed for papers related to a protein/variant.

    Args:
        query: Search term (e.g. "SOD1 A4V", "Tau P301L")
        email: Required by NCBI for API access
        api_key: Optional NCBI API key (enables 10 req/sec)
        max_results: Maximum papers to return
        year_range: Publication date range

    Returns:
        List of paper dicts with: pmid, title, abstract, authors,
        journal, pub_date, first_author, publication_year
    """
    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key

    try:
        # Build query with mutation/variant keyword
        search_query = (
            f"({query})[Title/Abstract] "
            f"AND (mutation[Title/Abstract] OR variant[Title/Abstract] "
            f"OR structure[Title/Abstract] OR folding[Title/Abstract])"
        )

        min_date, max_date = year_range.split(":")

        logger.info(f"Searching PubMed: {search_query}")

        handle = Entrez.esearch(
            db="pubmed",
            term=search_query,
            datetype="pdat",
            mindate=min_date,
            maxdate=max_date,
            retmax=max_results,
            retmode="xml",
        )
        result = Entrez.read(handle)
        handle.close()

        pmids = result.get("IdList", [])
        logger.info(f"Found {len(pmids)} papers")

        if not pmids:
            return []

        # Fetch abstracts
        handle = Entrez.efetch(
            db="pubmed",
            id=pmids,
            rettype="medline",
            retmode="text",
        )
        records = Medline.parse(handle)

        papers = []
        for record in records:
            # Extract DOI from AID field (format: "10.xxxx/yyyy [doi]")
            doi = None
            for aid in record.get("AID", []):
                if aid.endswith("[doi]"):
                    doi = aid.replace(" [doi]", "").strip()
                    break

            paper = {
                "pmid": record.get("PMID", ""),
                "title": record.get("TI", ""),
                "abstract": record.get("AB", ""),
                "authors": record.get("AU", []),
                "journal": record.get("JT", ""),
                "pub_date": record.get("DP", ""),
                "doi": doi,
                "first_author": _parse_first_author(record.get("AU", [])),
                "publication_year": _parse_year(record.get("DP", "")),
            }
            if paper["abstract"]:
                papers.append(paper)

        handle.close()
        logger.info(f"Fetched {len(papers)} papers with abstracts")
        return papers

    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        raise
