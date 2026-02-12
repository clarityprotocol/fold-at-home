"""UniProt protein lookup and FASTA sequence download."""

import logging
from pathlib import Path
from typing import Any, Dict

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_FASTA_URL = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
    ),
    reraise=True,
)
def check_protein_exists(protein_name: str) -> Dict[str, Any]:
    """Check if a protein/gene exists in UniProt (human proteome).

    Args:
        protein_name: Protein or gene name (e.g. "SOD1", "Tau", "MAPT")

    Returns:
        Dict with: found, accession, gene_symbol, protein_name, disease, error
    """
    not_found = {
        "found": False,
        "accession": None,
        "gene_symbol": None,
        "protein_name": None,
        "disease": None,
        "error": None,
    }

    try:
        params = {
            "query": f"(gene:{protein_name} OR protein_name:{protein_name}) AND (organism_id:9606)",
            "format": "json",
            "size": "1",
            "fields": "accession,gene_names,protein_name,cc_disease",
        }
        response = httpx.get(UNIPROT_SEARCH_URL, params=params, timeout=15.0)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            return not_found

        entry = results[0]
        accession = entry.get("primaryAccession")
        genes = entry.get("genes", [])
        gene_symbol = genes[0].get("geneName", {}).get("value") if genes else None

        prot_desc = entry.get("proteinDescription", {})
        rec_name = prot_desc.get("recommendedName", {})
        full_name = rec_name.get("fullName", {}).get("value") if rec_name else None

        # Extract disease from comments
        disease = None
        comments = entry.get("comments", [])
        for comment in comments:
            if comment.get("commentType") == "DISEASE":
                disease_obj = comment.get("disease", {})
                disease = disease_obj.get("diseaseId")
                if disease:
                    break

        return {
            "found": True,
            "accession": accession,
            "gene_symbol": gene_symbol,
            "protein_name": full_name,
            "disease": disease,
            "error": None,
        }

    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException):
        raise  # Let tenacity retry
    except Exception as e:
        logger.error(f"UniProt check failed for '{protein_name}': {e}")
        return {**not_found, "error": str(e)}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
    ),
    reraise=True,
)
def fetch_fasta(accession: str, output_path: Path) -> Path:
    """Download FASTA sequence from UniProt.

    Args:
        accession: UniProt accession (e.g. "P00441")
        output_path: Where to save the .fasta file

    Returns:
        Path to saved FASTA file
    """
    url = UNIPROT_FASTA_URL.format(accession=accession)
    response = httpx.get(url, timeout=15.0)
    response.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response.text)
    logger.info(f"Downloaded FASTA for {accession} to {output_path}")
    return output_path
