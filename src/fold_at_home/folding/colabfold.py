"""ColabFold folding backend."""

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .backend import FoldResult
from .preflight import (
    LARGE_PROTEIN_THRESHOLD,
    MemoryWatchdog,
    get_sequence_length,
    preflight,
    set_oom_priority,
)

logger = logging.getLogger(__name__)


class ColabFoldBackend:
    """Run structure prediction via colabfold_batch."""

    def __init__(self, config):
        self.config = config

    def is_available(self) -> tuple[bool, str]:
        binary = shutil.which(self.config.colabfold_path)
        if binary:
            return True, f"ColabFold found at {binary}"
        return False, (
            f"colabfold_batch not found (looked for '{self.config.colabfold_path}'). "
            "Install ColabFold: https://github.com/sokrypton/ColabFold"
        )

    def fold(self, fasta_path: Path, output_dir: Path) -> FoldResult:
        # Pre-launch safety checks
        if self.config.memory_watchdog:
            ok, msg = preflight()
            if not ok:
                return FoldResult(success=False, error=f"Preflight failed: {msg}")

        # Build command
        cmd = [self.config.colabfold_path, str(fasta_path), str(output_dir)]

        if self.config.gpu_device:
            cmd.extend(["--gpu-device", self.config.gpu_device])

        # Reduce models and MSA for large proteins
        seq_len = get_sequence_length(fasta_path)
        num_models = self.config.num_models
        if seq_len > LARGE_PROTEIN_THRESHOLD:
            cmd.extend(["--num-models", "3", "--max-msa", "256:2048"])
            logger.info(f"Large protein ({seq_len} residues) — using reduced models/MSA")
        else:
            cmd.extend(["--num-models", str(num_models)])

        logger.info(f"Running: {' '.join(cmd)}")

        output_dir.mkdir(parents=True, exist_ok=True)
        start = time.time()
        watchdog: Optional[MemoryWatchdog] = None

        try:
            # Use Popen to get PID for watchdog monitoring
            preexec = set_oom_priority if self.config.memory_watchdog else None
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=preexec,
            )

            # Start memory watchdog
            if self.config.memory_watchdog:
                watchdog = MemoryWatchdog(process.pid)
                watchdog.start()

            # Stream output
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    logger.info(f"[ColabFold] {line}")

            return_code = process.wait()
            elapsed = time.time() - start

            if watchdog and watchdog.killed:
                return FoldResult(
                    success=False,
                    elapsed_seconds=elapsed,
                    error="Killed by memory watchdog — protein too large or memory leak",
                )

            if return_code != 0:
                return FoldResult(
                    success=False,
                    elapsed_seconds=elapsed,
                    error=f"ColabFold exited with code {return_code}",
                )

            # Find output files
            pdb_file = self._find_best_pdb(output_dir)
            scores_file = self._find_scores(output_dir)

            return FoldResult(
                success=True,
                pdb_file=pdb_file,
                scores_file=scores_file,
                elapsed_seconds=elapsed,
            )

        except FileNotFoundError:
            return FoldResult(
                success=False,
                elapsed_seconds=time.time() - start,
                error=f"colabfold_batch not found: {self.config.colabfold_path}",
            )
        except Exception as e:
            return FoldResult(
                success=False,
                elapsed_seconds=time.time() - start,
                error=str(e),
            )
        finally:
            if watchdog:
                watchdog.stop()

    def _find_best_pdb(self, output_dir: Path) -> Optional[Path]:
        """Find the best-ranked PDB from ColabFold output."""
        # ColabFold names: *_relaxed_rank_001_*.pdb or *_unrelaxed_rank_001_*.pdb
        relaxed = sorted(output_dir.glob("*_relaxed_rank_001_*.pdb"))
        if relaxed:
            return relaxed[0]

        unrelaxed = sorted(output_dir.glob("*_unrelaxed_rank_001_*.pdb"))
        if unrelaxed:
            return unrelaxed[0]

        # Fallback: any PDB
        pdbs = sorted(output_dir.glob("*.pdb"))
        return pdbs[0] if pdbs else None

    def _find_scores(self, output_dir: Path) -> Optional[Path]:
        """Find score JSON from ColabFold output."""
        scores = sorted(output_dir.glob("*scores_rank_001_*.json"))
        if scores:
            return scores[0]

        scores = sorted(output_dir.glob("*scores*.json"))
        return scores[0] if scores else None
