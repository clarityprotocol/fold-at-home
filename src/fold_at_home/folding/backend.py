"""Folding backend protocol and factory."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass
class FoldResult:
    """Result of a folding run."""
    success: bool
    pdb_file: Optional[Path] = None
    scores_file: Optional[Path] = None
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


class FoldingBackend(Protocol):
    """Protocol for folding backends (ColabFold, AlphaFold, etc.)."""

    def is_available(self) -> tuple[bool, str]:
        """Check if the backend is installed and ready.

        Returns:
            (available, message)
        """
        ...

    def fold(self, fasta_path: Path, output_dir: Path) -> FoldResult:
        """Run structure prediction on a FASTA file.

        Args:
            fasta_path: Path to input .fasta file
            output_dir: Directory for output files

        Returns:
            FoldResult with success status and output paths
        """
        ...


def get_backend(config) -> FoldingBackend:
    """Factory: return the configured folding backend.

    Args:
        config: FoldingConfig with backend name and paths

    Returns:
        FoldingBackend instance

    Raises:
        ValueError: if backend name is not recognized
    """
    if config.backend == "colabfold":
        from .colabfold import ColabFoldBackend
        return ColabFoldBackend(config)
    elif config.backend == "alphafold":
        from .alphafold import AlphaFoldBackend
        return AlphaFoldBackend(config)
    else:
        raise ValueError(f"Unknown folding backend: {config.backend}")
