"""RMSD calculation for protein structure comparison.

Compares variant structure to wild-type downloaded from AlphaFold DB.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from Bio.PDB import PDBParser, Superimposer

logger = logging.getLogger(__name__)


def calculate_rmsd(ref_pdb: Path, target_pdb: Path) -> Optional[dict]:
    """Calculate RMSD between two structures using CA atoms.

    Args:
        ref_pdb: Reference (wild-type) structure
        target_pdb: Target (variant) structure

    Returns:
        {
            "rmsd_before_alignment": float,
            "rmsd_after_alignment": float,
            "num_atoms_aligned": int
        }
        Returns None if alignment fails.
    """
    parser = PDBParser(QUIET=True)

    try:
        ref_structure = parser.get_structure("reference", str(ref_pdb))
        target_structure = parser.get_structure("target", str(target_pdb))

        ref_chain = next(ref_structure[0].get_chains())
        target_chain = next(target_structure[0].get_chains())

        ref_ca = [a for a in ref_chain.get_atoms() if a.get_name() == "CA"]
        target_ca = [a for a in target_chain.get_atoms() if a.get_name() == "CA"]

        if not ref_ca or not target_ca:
            logger.warning("No CA atoms found in one or both structures")
            return None

        if len(ref_ca) != len(target_ca):
            logger.error(
                f"Mismatched CA atom counts: ref={len(ref_ca)}, target={len(target_ca)}"
            )
            return None

        # Superimpose
        superimposer = Superimposer()
        superimposer.set_atoms(ref_ca, target_ca)

        # RMSD before alignment
        ref_coords = np.array([a.get_coord() for a in ref_ca])
        target_coords = np.array([a.get_coord() for a in target_ca])
        rmsd_before = np.sqrt(np.mean(np.sum((ref_coords - target_coords) ** 2, axis=1)))

        return {
            "rmsd_before_alignment": float(rmsd_before),
            "rmsd_after_alignment": float(superimposer.rms),
            "num_atoms_aligned": len(ref_ca),
        }

    except Exception as e:
        logger.error(f"RMSD calculation failed: {e}", exc_info=True)
        return None


def calculate_variant_rmsd(
    variant_pdb: Path,
    uniprot_id: str,
    cache_dir: Optional[Path] = None,
) -> Optional[dict]:
    """Calculate RMSD between variant and wild-type from AlphaFold DB.

    Downloads wild-type structure if not already cached.

    Args:
        variant_pdb: Path to variant PDB file
        uniprot_id: UniProt accession for wild-type lookup
        cache_dir: Directory to cache downloaded wild-type PDB

    Returns:
        RMSD result dict with wild_type_source and wild_type_uniprot,
        or None if comparison fails.
    """
    from .alphafold_db import download_alphafold_structure

    if cache_dir is None:
        cache_dir = variant_pdb.parent

    # Check for cached wild-type
    cached = cache_dir / f"{uniprot_id}_wild_type.pdb"
    if cached.exists():
        wild_type_pdb = cached
    else:
        wild_type_pdb = download_alphafold_structure(uniprot_id, cache_dir)

    if not wild_type_pdb:
        logger.warning(f"Could not get wild-type structure for {uniprot_id}")
        return None

    result = calculate_rmsd(wild_type_pdb, variant_pdb)
    if result:
        result["wild_type_source"] = "alphafold_db"
        result["wild_type_uniprot"] = uniprot_id

    return result
