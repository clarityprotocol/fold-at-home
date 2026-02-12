"""pLDDT confidence analysis for AlphaFold/ColabFold predictions.

Extracts pLDDT scores from PDB B-factor field and identifies destabilized regions.
AlphaFold stores prediction confidence (pLDDT) in the B-factor field of PDB files.
"""

from pathlib import Path
from typing import Union

import numpy as np
from Bio.PDB import PDBParser


def analyze_plddt_confidence(pdb_file: Union[Path, str]) -> dict:
    """Extract pLDDT scores and identify destabilized regions.

    Args:
        pdb_file: Path to AlphaFold/ColabFold PDB file

    Returns:
        Dictionary with confidence metrics:
        {
            "avg_plddt": float,
            "min_plddt": float,
            "max_plddt": float,
            "confidence_distribution": {
                "very_high_90_100": int,
                "confident_70_90": int,
                "low_50_70": int,
                "very_low_0_50": int
            },
            "destabilized_regions": [
                {"start": int, "end": int, "length": int, "avg_plddt": float}
            ],
            "num_destabilized_residues": int,
            "percent_destabilized": float
        }
    """
    pdb_file = Path(pdb_file)
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", pdb_file)

    # Extract pLDDT from B-factor field (AlphaFold stores pLDDT there)
    residue_plddts = []
    residue_ids = []

    for model in structure:
        for chain in model:
            for residue in chain:
                if "CA" in residue:
                    ca_atom = residue["CA"]
                    residue_plddts.append(ca_atom.bfactor)
                    residue_ids.append(residue.id[1])

    plddts = np.array(residue_plddts)

    # Classify confidence regions (per AlphaFold guidelines)
    very_high = np.sum(plddts >= 90)
    confident = np.sum((plddts >= 70) & (plddts < 90))
    low = np.sum((plddts >= 50) & (plddts < 70))
    very_low = np.sum(plddts < 50)

    # Identify destabilized regions (pLDDT < 70)
    destabilized_threshold = 70
    destabilized_mask = plddts < destabilized_threshold

    # Find contiguous destabilized regions
    destabilized_regions = []
    in_region = False
    region_start = None
    region_start_idx = None

    for i, (res_id, is_destabilized) in enumerate(zip(residue_ids, destabilized_mask)):
        if is_destabilized and not in_region:
            region_start = res_id
            region_start_idx = i
            in_region = True
        elif not is_destabilized and in_region:
            destabilized_regions.append({
                "start": int(region_start),
                "end": int(residue_ids[i - 1]),
                "length": i - region_start_idx,
                "avg_plddt": float(np.mean(plddts[region_start_idx:i]))
            })
            in_region = False

    if in_region:
        destabilized_regions.append({
            "start": int(region_start),
            "end": int(residue_ids[-1]),
            "length": len(residue_ids) - region_start_idx,
            "avg_plddt": float(np.mean(plddts[region_start_idx:]))
        })

    return {
        "avg_plddt": float(np.mean(plddts)),
        "min_plddt": float(np.min(plddts)),
        "max_plddt": float(np.max(plddts)),
        "confidence_distribution": {
            "very_high_90_100": int(very_high),
            "confident_70_90": int(confident),
            "low_50_70": int(low),
            "very_low_0_50": int(very_low)
        },
        "destabilized_regions": destabilized_regions,
        "num_destabilized_residues": int(np.sum(destabilized_mask)),
        "percent_destabilized": float(100 * np.sum(destabilized_mask) / len(plddts))
    }
