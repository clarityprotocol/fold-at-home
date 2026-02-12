"""CLI entry point for fold-at-home."""

import shutil
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import load_config, create_default_config, CONFIG_FILE

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="fold-at-home")
def main():
    """Predict protein structures and generate AI-powered research summaries."""
    pass


@main.command()
@click.argument("protein", required=False)
@click.argument("variant", required=False)
@click.option("--fasta", type=click.Path(exists=True), help="Path to .fasta file")
@click.option("--protein", "protein_opt", help="Protein name (when using --fasta)")
@click.option("--variant", "variant_opt", help="Variant notation (when using --fasta)")
@click.option("--rationale", help="Why this fold matters (included in summary)")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--skip-fold", is_flag=True, help="Skip folding, analyze existing results")
@click.option("--skip-papers", is_flag=True, help="Skip PubMed search")
@click.option("--skip-summary", is_flag=True, help="Skip AI summary generation")
def fold(protein, variant, fasta, protein_opt, variant_opt, rationale, output, skip_fold, skip_papers, skip_summary):
    """Predict structure and generate research summary for a protein variant.

    \b
    Examples:
      fold-at-home fold SOD1 A4V
      fold-at-home fold SOD1 A4V --rationale "ALS-linked variant"
      fold-at-home fold --fasta ~/my_protein.fasta --protein SOD1 --variant A4V
    """
    config = load_config()

    # Resolve protein/variant from positional args or options
    protein = protein or protein_opt
    variant = variant or variant_opt

    if not protein and not fasta:
        console.print("[red]Error:[/red] Provide a protein name or --fasta path.")
        console.print("  fold-at-home fold SOD1 A4V")
        console.print("  fold-at-home fold --fasta ~/my_protein.fasta --protein SOD1")
        raise SystemExit(1)

    # Resolve output directory
    if output:
        output_dir = Path(output)
    else:
        name = f"{protein}_{variant}" if variant else protein
        output_dir = Path(config.output.results_dir) / name

    fasta_path = Path(fasta) if fasta else None

    console.print(Panel(
        f"[bold]{protein or 'Custom FASTA'}[/bold]"
        + (f" [dim]{variant}[/dim]" if variant else "")
        + (f"\n{rationale}" if rationale else ""),
        title="fold-at-home",
        border_style="blue",
    ))

    from .pipeline import run_pipeline

    success = run_pipeline(
        protein=protein,
        variant=variant,
        fasta_path=fasta_path,
        rationale=rationale,
        output_dir=output_dir,
        config=config,
        skip_fold=skip_fold,
        skip_papers=skip_papers,
        skip_summary=skip_summary,
    )

    if success:
        console.print(Panel(
            f"Results written to [bold]{output_dir}[/bold]\n"
            f"  summary.md      — Human-readable summary\n"
            f"  metadata.json   — Structured data\n"
            f"  structure/      — PDB files\n"
            f"  analysis/       — pLDDT, RMSD results",
            title="Complete",
            border_style="green",
        ))
    else:
        console.print(Panel("Pipeline failed. Check errors above.", title="Failed", border_style="red"))
        raise SystemExit(1)


@main.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--interval", default=None, type=int, help="Poll interval in seconds")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
def watch(directory, interval, output):
    """Watch a folder for .fasta files and process them automatically.

    \b
    Example:
      fold-at-home watch ~/my_folds/
      fold-at-home watch ~/my_folds/ --interval 30
    """
    config = load_config()
    poll_interval = interval or config.watch.poll_interval
    output_dir = Path(output) if output else Path(config.output.results_dir)

    console.print(Panel(
        f"Watching: [bold]{directory}[/bold]\n"
        f"Output:   {output_dir}\n"
        f"Interval: {poll_interval}s\n\n"
        f"[dim]Drop .fasta files into the watch folder to process them.\n"
        f"Press Ctrl+C to stop.[/dim]",
        title="fold-at-home watch mode",
        border_style="blue",
    ))

    from .watcher.queue import FolderWatcher

    watcher = FolderWatcher(
        watch_dir=Path(directory),
        output_dir=output_dir,
        config=config,
        interval=poll_interval,
    )
    watcher.run()


@main.command()
def init():
    """Create config file with interactive setup."""
    if CONFIG_FILE.exists():
        if not click.confirm(f"Config already exists at {CONFIG_FILE}. Overwrite?"):
            console.print("Keeping existing config.")
            return

    config_path = create_default_config()
    console.print(Panel(
        f"Config created at [bold]{config_path}[/bold]\n\n"
        f"Edit this file to set:\n"
        f"  1. Folding backend (colabfold or alphafold)\n"
        f"  2. AI provider + API key\n"
        f"  3. PubMed email\n\n"
        f"Then run: [bold]fold-at-home status[/bold] to verify",
        title="Configuration Created",
        border_style="green",
    ))


@main.command()
def status():
    """Show configuration and system status."""
    config = load_config()

    # Config file
    config_status = "[green]Found[/green]" if CONFIG_FILE.exists() else "[yellow]Not found[/yellow] (using defaults)"

    # Folding backend
    backend = config.folding.backend
    if backend == "colabfold":
        binary = shutil.which(config.folding.colabfold_path)
        backend_status = f"[green]Found at {binary}[/green]" if binary else "[red]Not found[/red]"
    elif backend == "alphafold":
        binary = shutil.which(config.folding.alphafold_path) if config.folding.alphafold_path else None
        backend_status = f"[green]Found at {binary}[/green]" if binary else "[red]Not configured[/red]"
    else:
        backend_status = f"[red]Unknown backend: {backend}[/red]"

    # AI provider
    provider = config.ai.provider
    api_key = config.ai.get_api_key()
    if provider == "ollama":
        ai_status = f"Ollama at {config.ai.ollama_url}"
    elif api_key:
        ai_status = f"[green]{api_key[:8]}...{api_key[-4:]}[/green]"
    else:
        ai_status = "[red]No API key[/red]"

    table = Table(title="fold-at-home status", show_header=False, border_style="blue")
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    table.add_row("Version", __version__)
    table.add_row("Config", config_status)
    table.add_row("", "")
    table.add_row("Folding backend", backend)
    table.add_row("Backend binary", backend_status)
    table.add_row("GPU device", config.folding.gpu_device or "auto")
    table.add_row("", "")
    table.add_row("AI provider", provider)
    table.add_row("AI key/endpoint", ai_status)
    table.add_row("AI model", config.ai.model or "(provider default)")
    table.add_row("", "")
    table.add_row("PubMed email", config.pubmed.email)
    table.add_row("Results dir", config.output.results_dir)

    console.print(table)
