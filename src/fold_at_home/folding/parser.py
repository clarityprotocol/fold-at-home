"""Parse fold output files (score JSONs, PDB metadata)."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def parse_scores(scores_file: Path) -> Optional[list[float]]:
    """Parse pLDDT scores from ColabFold/AlphaFold score JSON.

    ColabFold score format: {"plddt": [float, ...], ...}
    AlphaFold score format: {"plddts": {"model_1": [float, ...], ...}}

    Args:
        scores_file: Path to score JSON file

    Returns:
        List of per-residue pLDDT scores, or None if parsing fails
    """
    try:
        with open(scores_file) as f:
            data = json.load(f)

        # ColabFold format
        if "plddt" in data:
            return data["plddt"]

        # AlphaFold format (take first model's scores)
        if "plddts" in data:
            plddts = data["plddts"]
            if isinstance(plddts, dict):
                first_key = next(iter(plddts))
                return plddts[first_key]
            return plddts

        # Try generic pLDDT key variations
        for key in ["plddt_scores", "pLDDT", "confidence"]:
            if key in data:
                return data[key]

        logger.warning(f"No pLDDT scores found in {scores_file}")
        return None

    except Exception as e:
        logger.error(f"Failed to parse scores from {scores_file}: {e}")
        return None


def find_best_pdb(output_dir: Path) -> Optional[Path]:
    """Find the best-ranked PDB file in a fold output directory.

    Checks ColabFold naming first, then AlphaFold, then any PDB.
    """
    # ColabFold: *_relaxed_rank_001_*.pdb
    relaxed = sorted(output_dir.glob("*_relaxed_rank_001_*.pdb"))
    if relaxed:
        return relaxed[0]

    unrelaxed = sorted(output_dir.glob("*_unrelaxed_rank_001_*.pdb"))
    if unrelaxed:
        return unrelaxed[0]

    # AlphaFold: ranked_0.pdb
    ranked = sorted(output_dir.glob("**/ranked_0.pdb"))
    if ranked:
        return ranked[0]

    # Any PDB
    pdbs = sorted(output_dir.glob("**/*.pdb"))
    return pdbs[0] if pdbs else None
