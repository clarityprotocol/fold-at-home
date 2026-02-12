"""Watch mode: poll a directory for .fasta files and process them."""

import logging
import re
import shutil
import signal
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..config import Config

logger = logging.getLogger(__name__)
console = Console()


class FolderWatcher:
    """Watch a directory for .fasta files and run the pipeline on each."""

    def __init__(
        self,
        watch_dir: Path,
        output_dir: Path,
        config: Config,
        interval: int = 60,
    ):
        self.watch_dir = watch_dir
        self.output_dir = output_dir
        self.config = config
        self.interval = interval
        self.running = True

        # Track processed files
        self._processed: set[str] = set()

    def parse_fasta_name(self, fasta_path: Path) -> tuple[Optional[str], Optional[str]]:
        """Extract protein name and variant from FASTA filename.

        Supported formats:
            SOD1_A4V.fasta       -> ("SOD1", "A4V")
            01_SOD1_A4V.fasta    -> ("SOD1", "A4V")
            tau_P301L.fasta      -> ("tau", "P301L")
            my_protein.fasta     -> ("my_protein", None)

        Variant is detected by pattern: single letter + digits + single letter
        """
        name = fasta_path.stem

        # Remove leading number prefix (01_, 02_)
        name = re.sub(r"^\d+_", "", name)

        # Try to split protein_variant
        # Variant patterns: A4V, P301L, G2019S, R521C
        variant_pattern = r"_([A-Z]\d+[A-Z])$"
        match = re.search(variant_pattern, name)

        if match:
            variant = match.group(1)
            protein = name[: match.start()]
            return protein, variant

        return name, None

    def get_queue_files(self) -> list[Path]:
        """Get unprocessed .fasta files, sorted by name."""
        if not self.watch_dir.exists():
            return []

        files = []
        for f in sorted(self.watch_dir.glob("*.fasta")):
            if f.name not in self._processed:
                files.append(f)
        return files

    def process_one(self, fasta_path: Path) -> bool:
        """Process a single FASTA file through the pipeline.

        Returns True on success.
        """
        protein, variant = self.parse_fasta_name(fasta_path)

        name = f"{protein}_{variant}" if variant else protein
        result_dir = self.output_dir / name

        console.print(f"\n[bold]Processing:[/bold] {fasta_path.name}")
        console.print(f"  Protein: {protein or 'Unknown'}")
        if variant:
            console.print(f"  Variant: {variant}")
        console.print(f"  Output:  {result_dir}")

        from ..pipeline import run_pipeline

        success = run_pipeline(
            protein=protein,
            variant=variant,
            fasta_path=fasta_path,
            rationale=None,
            output_dir=result_dir,
            config=self.config,
        )

        if success:
            self._processed.add(fasta_path.name)

            # Archive or leave in place
            if self.config.watch.archive_processed:
                archive_dir = self.watch_dir / "archive"
                archive_dir.mkdir(exist_ok=True)
                shutil.move(str(fasta_path), str(archive_dir / fasta_path.name))
                console.print(f"  [dim]Archived: {fasta_path.name}[/dim]")
            else:
                # Create done marker
                done_file = self.watch_dir / f"{fasta_path.stem}.done"
                done_file.touch()

            console.print(f"  [green]Complete:[/green] {name}")
        else:
            console.print(f"  [red]Failed:[/red] {name}")

        return success

    def run(self):
        """Main watch loop."""
        logger.info(f"Watching {self.watch_dir} (interval: {self.interval}s)")

        # Signal handlers for graceful shutdown
        def shutdown(signum, frame):
            logger.info(f"Received signal {signum}, stopping...")
            self.running = False

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        while self.running:
            queue = self.get_queue_files()

            if queue:
                console.print(f"\n[bold]{len(queue)} file(s) in queue[/bold]")
                # Process next file
                self.process_one(queue[0])
            else:
                logger.debug(f"No new files, sleeping {self.interval}s")

            # Sleep in chunks for responsive shutdown
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

        console.print("\n[dim]Watch mode stopped.[/dim]")
