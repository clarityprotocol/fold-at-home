"""Download wild-type structures from AlphaFold Database."""

import logging
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)


def get_retry_session() -> requests.Session:
    """Create a requests Session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def download_alphafold_structure(uniprot_id: str, output_dir: Path) -> Optional[Path]:
    """Download AlphaFold predicted structure for a UniProt ID.

    Args:
        uniprot_id: UniProt accession (e.g. "P00441")
        output_dir: Directory to save PDB file

    Returns:
        Path to downloaded PDB file, or None if not available
    """
    session = get_retry_session()

    try:
        # Query AlphaFold DB API
        api_url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
        response = session.get(api_url, timeout=10)

        if response.status_code == 404:
            logger.info(f"Protein {uniprot_id} not in AlphaFold DB")
            return None

        if response.status_code != 200:
            logger.warning(f"AlphaFold API returned {response.status_code}")
            return None

        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        else:
            return None

        # Download PDB file
        pdb_url = data.get("pdbUrl")
        if not pdb_url:
            logger.warning(f"No PDB URL for {uniprot_id}")
            return None

        pdb_response = session.get(pdb_url, timeout=30)
        if pdb_response.status_code != 200:
            logger.warning(f"Failed to download PDB for {uniprot_id}")
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{uniprot_id}_wild_type.pdb"
        output_path.write_bytes(pdb_response.content)

        logger.info(f"Downloaded wild-type structure for {uniprot_id}")
        return output_path

    except Exception as e:
        logger.error(f"Error downloading AlphaFold structure for {uniprot_id}: {e}")
        return None
