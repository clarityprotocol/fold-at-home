"""Main pipeline orchestrator for fold-at-home.

Coordinates: folding -> analysis -> papers -> summary -> output
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from .config import Config

logger = logging.getLogger(__name__)
console = Console()


def run_pipeline(
    protein: Optional[str],
    variant: Optional[str],
    fasta_path: Optional[Path],
    rationale: Optional[str],
    output_dir: Path,
    config: Config,
    skip_fold: bool = False,
    skip_papers: bool = False,
    skip_summary: bool = False,
) -> bool:
    """Run the full fold-at-home pipeline.

    Steps:
        1. Resolve protein info via UniProt
        2. Generate/locate FASTA
        3. Run folding backend
        4. Parse fold output
        5. Analyze structure (pLDDT, RMSD)
        6. Fetch PubMed papers
        7. Generate AI summary
        8. Write output files

    Returns True on success, False on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "protein_name": protein,
        "variant": variant,
        "rationale": rationale,
        "fold_at_home_version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uniprot_id": None,
        "disease": None,
    }

    # === Step 1: UniProt lookup ===
    uniprot_info = None
    if protein:
        with console.status("[bold]Looking up protein in UniProt..."):
            try:
                from .discovery.uniprot import check_protein_exists
                uniprot_info = check_protein_exists(protein)
                if uniprot_info.get("found"):
                    metadata["uniprot_id"] = uniprot_info.get("accession")
                    metadata["disease"] = uniprot_info.get("disease")
                    gene_symbol = uniprot_info.get("gene_symbol")
                    if gene_symbol:
                        console.print(f"  UniProt: [green]{gene_symbol}[/green] ({uniprot_info.get('protein_name', '')})")
                else:
                    console.print(f"  UniProt: [yellow]Not found[/yellow] (continuing anyway)")
            except Exception as e:
                console.print(f"  UniProt: [yellow]Lookup failed ({e})[/yellow]")

    # === Step 2: FASTA ===
    if not fasta_path and not skip_fold:
        if uniprot_info and uniprot_info.get("found"):
            with console.status("[bold]Fetching sequence from UniProt..."):
                try:
                    from .discovery.uniprot import fetch_fasta
                    fasta_path = output_dir / f"{protein}.fasta"
                    fetch_fasta(uniprot_info["accession"], fasta_path)
                    console.print(f"  FASTA: [green]Downloaded[/green]")
                except Exception as e:
                    console.print(f"  [red]Error:[/red] Could not fetch FASTA: {e}")
                    console.print("  Provide a FASTA file with --fasta")
                    return False
        else:
            console.print("[red]Error:[/red] No FASTA file and protein not found in UniProt.")
            console.print("  Provide a FASTA file with --fasta")
            return False

    # === Step 3: Folding ===
    fold_output_dir = output_dir / "structure"
    fold_output_dir.mkdir(exist_ok=True)
    pdb_file = None
    scores_file = None

    if not skip_fold:
        console.print("\n[bold]Running structure prediction...[/bold]")
        try:
            from .folding.backend import get_backend
            backend = get_backend(config.folding)

            available, msg = backend.is_available()
            if not available:
                console.print(f"  [red]Error:[/red] {msg}")
                console.print("  Run [bold]fold-at-home status[/bold] to check your setup")
                return False

            result = backend.fold(fasta_path, fold_output_dir)
            if not result.success:
                console.print(f"  [red]Folding failed:[/red] {result.error}")
                return False

            pdb_file = result.pdb_file
            scores_file = result.scores_file
            metadata["folding"] = {
                "backend": config.folding.backend,
                "elapsed_seconds": result.elapsed_seconds,
                "pdb_file": str(pdb_file.relative_to(output_dir)) if pdb_file else None,
            }
            console.print(f"  [green]Folding complete[/green] ({result.elapsed_seconds:.0f}s)")
        except Exception as e:
            console.print(f"  [red]Folding error:[/red] {e}")
            return False
    else:
        # Look for existing PDB in output dir
        pdbs = list(fold_output_dir.glob("*.pdb"))
        if pdbs:
            pdb_file = pdbs[0]
            console.print(f"  Using existing PDB: {pdb_file.name}")
        else:
            console.print("[yellow]No PDB file found. Skipping analysis.[/yellow]")

    # === Step 4: Parse fold output ===
    plddt_scores = None
    if scores_file and scores_file.exists():
        try:
            from .folding.parser import parse_scores
            plddt_scores = parse_scores(scores_file)
        except Exception as e:
            logger.warning(f"Score parsing failed: {e}")

    # Copy visualization PNGs
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(exist_ok=True)
    for png in fold_output_dir.glob("*.png"):
        shutil.copy2(png, viz_dir / png.name)

    # === Step 5: Analysis ===
    analysis_dir = output_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    confidence_result = None
    rmsd_result = None

    if pdb_file and pdb_file.exists():
        # pLDDT confidence
        with console.status("[bold]Analyzing pLDDT confidence..."):
            try:
                from .analysis.confidence import analyze_plddt_confidence
                confidence_result = analyze_plddt_confidence(pdb_file)
                (analysis_dir / "confidence.json").write_text(
                    json.dumps(confidence_result, indent=2)
                )
                avg = confidence_result.get("avg_plddt", 0)
                console.print(f"  pLDDT: [green]{avg:.1f}[/green] average confidence")
            except Exception as e:
                console.print(f"  pLDDT: [yellow]Analysis failed ({e})[/yellow]")

        # Variant RMSD (only if we have a variant and UniProt ID)
        if variant and metadata.get("uniprot_id"):
            with console.status("[bold]Comparing to wild-type structure..."):
                try:
                    from .analysis.rmsd import calculate_variant_rmsd
                    rmsd_result = calculate_variant_rmsd(
                        variant_pdb=pdb_file,
                        uniprot_id=metadata["uniprot_id"],
                        cache_dir=output_dir / "structure",
                    )
                    (analysis_dir / "rmsd.json").write_text(
                        json.dumps(rmsd_result, indent=2)
                    )
                    rmsd_val = rmsd_result.get("rmsd_after_alignment", 0)
                    console.print(f"  RMSD:  [green]{rmsd_val:.2f} A[/green] vs wild-type")
                except Exception as e:
                    console.print(f"  RMSD:  [yellow]Comparison failed ({e})[/yellow]")

    metadata["analysis"] = {
        "confidence": confidence_result,
        "rmsd": rmsd_result,
    }

    # === Step 6: PubMed papers ===
    papers = []
    papers_dir = output_dir / "papers"
    papers_dir.mkdir(exist_ok=True)

    if not skip_papers:
        with console.status("[bold]Searching PubMed for related papers..."):
            try:
                from .discovery.pubmed import search_papers
                search_term = protein or ""
                if variant:
                    search_term += f" {variant}"
                papers = search_papers(
                    query=search_term,
                    email=config.pubmed.email,
                    api_key=config.pubmed.ncbi_api_key or None,
                    max_results=config.pubmed.max_papers,
                )
                (papers_dir / "papers.json").write_text(
                    json.dumps(papers, indent=2, default=str)
                )
                console.print(f"  Papers: [green]{len(papers)}[/green] found")
            except Exception as e:
                console.print(f"  Papers: [yellow]Search failed ({e})[/yellow]")

    # === Step 6b: Clinical enrichment (ClinVar + gnomAD) ===
    clinical_data = None
    gene_symbol = None

    if variant and uniprot_info and uniprot_info.get("found"):
        gene_symbol = uniprot_info.get("gene_symbol")

    if variant and gene_symbol:
        with console.status("[bold]Looking up clinical data (ClinVar + gnomAD)..."):
            try:
                from .discovery.enrichment import enrich_variant
                clinical_data = enrich_variant(
                    gene_symbol=gene_symbol,
                    variant_notation=variant,
                    email=config.pubmed.email,
                    ncbi_api_key=config.pubmed.ncbi_api_key or None,
                )
                if clinical_data:
                    sig = clinical_data.get("clinvar_significance")
                    af = clinical_data.get("gnomad_af")
                    if sig:
                        console.print(f"  ClinVar: [green]{sig}[/green]")
                    else:
                        console.print(f"  ClinVar: [dim]No entry found[/dim]")
                    if af is not None:
                        console.print(f"  gnomAD:  [green]AF={af:.2e}[/green]")
                    else:
                        console.print(f"  gnomAD:  [dim]Not in population database[/dim]")

                    metadata["clinical"] = clinical_data
                else:
                    console.print(f"  Clinical: [dim]No data available[/dim]")
            except Exception as e:
                console.print(f"  Clinical: [yellow]Lookup failed ({e})[/yellow]")

    # === Step 7: AI summary ===
    summary_text = None

    if not skip_summary:
        with console.status(f"[bold]Generating summary via {config.ai.provider}..."):
            try:
                from .ai.provider import get_provider
                from .ai.prompts import build_summary_prompt
                from .output.citations import build_works_cited_section, find_similar_papers
                from .output.markdown import assemble_summary

                provider = get_provider(config.ai)
                available, msg = provider.is_available()
                if not available:
                    console.print(f"  AI: [red]{msg}[/red]")
                else:
                    prompt, system_prompt = build_summary_prompt(
                        protein_name=protein,
                        variant=variant,
                        rationale=rationale,
                        disease=metadata.get("disease"),
                        uniprot_id=metadata.get("uniprot_id"),
                        confidence=confidence_result,
                        rmsd=rmsd_result,
                        papers=papers,
                        clinical_data=clinical_data,
                    )

                    result = provider.generate_summary(prompt, system_prompt)
                    if result:
                        works_cited = build_works_cited_section(papers, result.citations_used, result.citation_relevance)
                        similar = find_similar_papers(papers, result.citations_used)

                        summary_text = assemble_summary(
                            tldr=result.tldr,
                            detailed=result.detailed_summary,
                            works_cited=works_cited,
                            similar_research=similar,
                        )
                        metadata["summary"] = {
                            "ai_provider": config.ai.provider,
                            "ai_model": config.ai.model or "(default)",
                            "tldr": result.tldr,
                            "citations_used": result.citations_used,
                        }
                        console.print(f"  Summary: [green]Generated[/green]")
                    else:
                        console.print("  Summary: [yellow]AI returned no output[/yellow]")
            except Exception as e:
                console.print(f"  Summary: [yellow]Generation failed ({e})[/yellow]")

    # === Step 8: Write output ===
    if summary_text:
        (output_dir / "summary.md").write_text(summary_text)

    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str)
    )

    return True
