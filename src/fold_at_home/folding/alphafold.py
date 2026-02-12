"""AlphaFold folding backend (Docker or native)."""

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .backend import FoldResult

logger = logging.getLogger(__name__)


class AlphaFoldBackend:
    """Run structure prediction via AlphaFold (Docker or native install)."""

    def __init__(self, config):
        self.config = config

    def is_available(self) -> tuple[bool, str]:
        # Check for alphafold binary or docker
        if self.config.alphafold_path:
            binary = shutil.which(self.config.alphafold_path)
            if binary:
                return True, f"AlphaFold found at {binary}"

        # Check for Docker-based AlphaFold
        docker = shutil.which("docker")
        if docker:
            return True, "Docker available (will use alphafold Docker image)"

        return False, (
            "AlphaFold not found. Either:\n"
            "  1. Set alphafold_path in config to your AlphaFold binary\n"
            "  2. Install Docker for AlphaFold Docker mode\n"
            "See: https://github.com/google-deepmind/alphafold"
        )

    def fold(self, fasta_path: Path, output_dir: Path) -> FoldResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        start = time.time()

        try:
            if self.config.alphafold_path and shutil.which(self.config.alphafold_path):
                return self._run_native(fasta_path, output_dir, start)
            else:
                return self._run_docker(fasta_path, output_dir, start)
        except Exception as e:
            return FoldResult(
                success=False,
                elapsed_seconds=time.time() - start,
                error=str(e),
            )

    def _run_native(self, fasta_path: Path, output_dir: Path, start: float) -> FoldResult:
        """Run AlphaFold via native binary."""
        cmd = [
            self.config.alphafold_path,
            f"--fasta_paths={fasta_path}",
            f"--output_dir={output_dir}",
            "--model_preset=monomer",
            "--db_preset=reduced_dbs",
        ]

        if self.config.gpu_device:
            cmd.append(f"--gpu_devices={self.config.gpu_device}")

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_hours * 3600,
        )

        elapsed = time.time() - start

        if result.returncode != 0:
            return FoldResult(
                success=False,
                elapsed_seconds=elapsed,
                error=f"AlphaFold failed: {result.stderr[-500:] if result.stderr else 'unknown error'}",
            )

        pdb_file = self._find_pdb(output_dir)
        return FoldResult(
            success=True,
            pdb_file=pdb_file,
            elapsed_seconds=elapsed,
        )

    def _run_docker(self, fasta_path: Path, output_dir: Path, start: float) -> FoldResult:
        """Run AlphaFold via Docker."""
        cmd = [
            "docker", "run", "--rm",
            "--gpus", "all",
            "-v", f"{fasta_path.parent}:/input",
            "-v", f"{output_dir}:/output",
            "alphafold",
            f"--fasta_paths=/input/{fasta_path.name}",
            "--output_dir=/output",
            "--model_preset=monomer",
            "--db_preset=reduced_dbs",
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_hours * 3600,
        )

        elapsed = time.time() - start

        if result.returncode != 0:
            return FoldResult(
                success=False,
                elapsed_seconds=elapsed,
                error=f"AlphaFold Docker failed: {result.stderr[-500:] if result.stderr else 'unknown error'}",
            )

        pdb_file = self._find_pdb(output_dir)
        return FoldResult(
            success=True,
            pdb_file=pdb_file,
            elapsed_seconds=elapsed,
        )

    def _find_pdb(self, output_dir: Path) -> Optional[Path]:
        """Find PDB from AlphaFold output."""
        # AlphaFold outputs: ranked_0.pdb, ranked_1.pdb, ...
        ranked = sorted(output_dir.glob("**/ranked_0.pdb"))
        if ranked:
            return ranked[0]

        # Fallback to any PDB
        pdbs = sorted(output_dir.glob("**/*.pdb"))
        return pdbs[0] if pdbs else None
