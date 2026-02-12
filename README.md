# fold-at-home

Predict protein structures and generate AI-powered research summaries — locally, on your own hardware.

## What it does

1. **Looks up your protein** in UniProt (or uses your FASTA file)
2. **Folds it** via ColabFold or AlphaFold
3. **Analyzes the structure** — pLDDT confidence scores, RMSD vs wild-type
4. **Checks clinical databases** — ClinVar pathogenicity, gnomAD population frequency
5. **Finds relevant papers** on PubMed
6. **Generates a citation-backed summary** using Claude, GPT-4, or a local Ollama model
7. **Writes everything** to a clean results folder

## System requirements

| OS | Supported? | Notes |
|----|-----------|-------|
| **Linux** | Full support | Primary platform. Any distro with NVIDIA drivers + CUDA |
| **Windows (WSL2)** | Full support | Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) first, then follow Linux instructions inside WSL |
| **macOS** | Analysis only | No NVIDIA GPU = no folding. You can use `--skip-fold` to analyze PDB files from elsewhere and generate summaries |

ColabFold and AlphaFold require an **NVIDIA GPU with CUDA**. Apple Silicon (M1/M2/M3/M4) uses Metal, not CUDA, so folding cannot run natively on macOS. Everything else (analysis, papers, AI summary) works on any OS.

**macOS workaround:** Use the free [ColabFold Google Colab notebook](https://colab.research.google.com/github/sokrypton/ColabFold/blob/main/AlphaFold2.ipynb) to fold on Google's GPUs, download the results, then run `fold-at-home fold PROTEIN VARIANT --skip-fold` locally for the full analysis and AI summary. See [macOS workflow](#macos-workflow-google-colab) below.

**Minimum hardware for folding:**
- NVIDIA GPU with 8+ GB VRAM (GTX 1080 or better)
- 16 GB RAM (32 GB recommended for large proteins)
- 100 GB free disk space (ColabFold downloads databases on first run)

## Prerequisites

Before installing fold-at-home, you need a folding backend and a GPU.

### 1. Check your GPU

ColabFold and AlphaFold require an NVIDIA GPU with CUDA support.

```bash
# Verify NVIDIA drivers are installed
nvidia-smi

# You should see your GPU name, driver version, and CUDA version
# If this fails, install NVIDIA drivers first: https://www.nvidia.com/drivers
```

### 2. Install a folding backend

You need **one** of these. ColabFold is recommended — it's faster to install and run.

**Option A: ColabFold (recommended)**

ColabFold is a fast, optimized version of AlphaFold that uses MMseqs2 for sequence search.

```bash
# Install via conda (takes ~20 minutes)
# Full guide: https://github.com/sokrypton/ColabFold

# 1. Install Miniconda if you don't have it
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 2. Create ColabFold environment
conda create -n colabfold python=3.10 -y
conda activate colabfold

# 3. Install ColabFold
pip install colabfold[alphafold]

# 4. Verify it works
colabfold_batch --help
```

> **Disk space:** ColabFold downloads sequence databases on first run (~100 GB). Make sure you have space.

**Option B: AlphaFold**

Original DeepMind implementation. Slower but supports more features.

```bash
# Install via Docker (easiest)
# Full guide: https://github.com/google-deepmind/alphafold

docker pull alphafold
```

> **Disk space:** AlphaFold databases require ~2.5 TB. Consider ColabFold if space is limited.

### 3. Verify your backend is working

```bash
# ColabFold — should print help text
colabfold_batch --help

# AlphaFold Docker — should show the image
docker images | grep alphafold
```

### 4. Python 3.10+

```bash
python --version  # Should be 3.10 or higher
```

## Install fold-at-home

```bash
pip install fold-at-home

# With AI provider support (pick one or both):
pip install "fold-at-home[anthropic]"   # Claude
pip install "fold-at-home[openai]"      # GPT-4
pip install "fold-at-home[all]"         # Both

# Ollama (local AI) needs no extra package — just install Ollama separately
# https://ollama.com
```

## Setup

### 1. Create config file

```bash
fold-at-home init
```

This creates `~/.fold-at-home/config.toml` with default settings.

### 2. Edit your config

```bash
nano ~/.fold-at-home/config.toml
```

At minimum, set these:

```toml
[ai]
provider = "anthropic"                      # or "openai" or "ollama"
anthropic_api_key = "sk-ant-your-key-here"  # from console.anthropic.com

[pubmed]
email = "your-real@email.com"               # Required by NCBI (they may contact you about API usage)
```

### 3. Verify everything

```bash
fold-at-home status
```

You should see something like:

```
                        fold-at-home status
┌─────────────────┬──────────────────────────────────────┐
│ Version         │ 0.1.0                                │
│ Config          │ Found                                │
│                 │                                      │
│ Folding backend │ colabfold                            │
│ Backend binary  │ Found at /usr/local/bin/colabfold... │
│ GPU device      │ auto                                 │
│                 │                                      │
│ AI provider     │ anthropic                            │
│ AI key/endpoint │ sk-ant-a...xY2z                      │
│ AI model        │ (provider default)                   │
│                 │                                      │
│ PubMed email    │ your-real@email.com                  │
│ Results dir     │ ./results                            │
└─────────────────┴──────────────────────────────────────┘
```

**What to check:**
- **Backend binary** should say "Found at ..." (green). If it says "Not found", ColabFold/AlphaFold isn't in your PATH — set `colabfold_path` in config to the full path.
- **AI key/endpoint** should show a masked key. If it says "No API key", add your key to the config or set `ANTHROPIC_API_KEY` as an environment variable.

## Usage

### Single fold

```bash
# Basic: protein name + variant
fold-at-home fold SOD1 A4V

# With a rationale (included in the summary)
fold-at-home fold SOD1 A4V --rationale "ALS-linked variant"

# Using your own FASTA file
fold-at-home fold --fasta ~/my_protein.fasta --protein SOD1 --variant A4V

# Wild-type (no variant)
fold-at-home fold SOD1
```

**What happens when you run this:**

```
╭──────── fold-at-home ────────╮
│ SOD1 A4V                     │
│ ALS-linked variant           │
╰──────────────────────────────╯
  UniProt: SOD1 (Superoxide dismutase [Cu-Zn])
  FASTA: Downloaded

Running structure prediction...
  [ColabFold] Running model 1/5...
  [ColabFold] Running model 2/5...
  ...
  Folding complete (847s)

  pLDDT: 82.4 average confidence
  RMSD:  1.87 A vs wild-type
  ClinVar: Pathogenic
  gnomAD:  Not in population database
  Papers: 14 found
  Summary: Generated

╭──────── Complete ────────╮
│ Results: results/SOD1_A4V│
│   summary.md             │
│   metadata.json          │
│   structure/             │
│   analysis/              │
╰──────────────────────────╯
```

### Watch mode

Drop `.fasta` files into a folder and fold-at-home processes them automatically:

```bash
fold-at-home watch ~/my_folds/

# Custom poll interval (check every 30 seconds)
fold-at-home watch ~/my_folds/ --interval 30
```

**FASTA naming convention** — the filename tells fold-at-home what to fold:

```
SOD1_A4V.fasta         -> protein=SOD1, variant=A4V
01_tau_P301L.fasta     -> protein=tau, variant=P301L (number prefix for queue order)
alpha-synuclein.fasta  -> protein=alpha-synuclein, no variant
```

Processed files are moved to `~/my_folds/archive/` after folding.

### Skip steps

Already folded? No API key? Offline? On macOS? Run only the parts you need:

```bash
# Skip folding — just analyze existing PDB + generate summary
# (this is how macOS users run fold-at-home — fold on a server, analyze locally)
fold-at-home fold SOD1 A4V --skip-fold

# Skip AI summary (no API key needed)
fold-at-home fold SOD1 A4V --skip-summary

# Skip PubMed search (works offline)
fold-at-home fold SOD1 A4V --skip-papers

# Combine flags
fold-at-home fold SOD1 A4V --skip-fold --skip-papers
```

> **macOS users:** See the [macOS workflow](#macos-workflow-google-colab) section below for step-by-step instructions using Google Colab.

### macOS workflow (Google Colab)

If you don't have an NVIDIA GPU (macOS, older laptops, etc.), you can fold proteins for free using Google Colab and then run the analysis locally:

**1. Fold on Google Colab**

Open the free ColabFold notebook: [ColabFold on Google Colab](https://colab.research.google.com/github/sokrypton/ColabFold/blob/main/AlphaFold2.ipynb)

- Paste your protein sequence into the `query_sequence` field
- Set `jobname` to something like `SOD1_A4V`
- Click **Runtime → Run all**
- When finished, Colab downloads a zip file with the PDB files and score JSONs

**2. Copy results into fold-at-home's structure**

```bash
# Create the results directory
mkdir -p results/SOD1_A4V/structure

# Unzip and copy PDB + score files
unzip SOD1_A4V.result.zip -d results/SOD1_A4V/structure/

# You should now have .pdb and _scores_*.json files in structure/
ls results/SOD1_A4V/structure/
```

**3. Run the analysis locally**

```bash
fold-at-home fold SOD1 A4V --skip-fold
```

This runs everything except the fold: pLDDT analysis, RMSD vs wild-type, ClinVar + gnomAD lookup, PubMed papers, and AI summary. You get the same `summary.md` and `metadata.json` as a full run.

**Want to contribute GPU power to protein research?** Join the Clarity Protocol team on [Folding@Home](https://foldingathome.org/) — **Team ID: 1067834**. Folding@Home runs protein folding simulations on your computer when it's idle, contributing to real medical research. Any OS, any hardware.

## Output

Each fold produces a results directory. By default, results go to `./results/` relative to where you ran the command. You can change this in your config (`results_dir`) or with `--output`.

```
results/SOD1_A4V/
├── summary.md              # The main output — human-readable research summary
├── metadata.json           # All structured data (protein, analysis, clinical, citations)
├── PROTEIN.fasta           # The FASTA sequence used for folding
├── structure/              # PDB structure files
│   ├── *_rank_001_*.pdb    # Best predicted structure (rank 1)
│   ├── *_rank_002_*.pdb    # Second best prediction
│   ├── *_rank_003_*.pdb    # Third (if num_models >= 3)
│   ├── *_wild_type.pdb     # Wild-type structure from AlphaFold DB (for RMSD)
│   └── *_scores_*.json     # Raw prediction confidence scores from ColabFold
├── analysis/
│   ├── confidence.json     # pLDDT confidence scores + destabilized regions
│   └── rmsd.json           # RMSD comparison to wild-type structure
├── visualizations/         # PNG images generated by ColabFold
│   ├── *_plddt.png         # Per-residue confidence plot
│   ├── *_pae.png           # Predicted aligned error matrix
│   └── *_coverage.png      # Sequence alignment coverage
└── papers/
    └── papers.json         # PubMed search results with abstracts and DOIs
```

### Finding and viewing your results

```bash
# See where your results went
ls results/

# Read the summary
cat results/SOD1_A4V/summary.md

# View the confidence plot (Linux with GUI)
xdg-open results/SOD1_A4V/visualizations/*plddt.png

# View all visualizations
for f in results/SOD1_A4V/visualizations/*.png; do xdg-open "$f"; done

# View on WSL2 (Windows)
explorer.exe results/SOD1_A4V/visualizations/

# View structured data
cat results/SOD1_A4V/metadata.json | python -m json.tool

# View clinical data specifically
cat results/SOD1_A4V/metadata.json | python -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('clinical',{}), indent=2))"

# View analysis results
cat results/SOD1_A4V/analysis/confidence.json | python -m json.tool
cat results/SOD1_A4V/analysis/rmsd.json | python -m json.tool

# List all papers found
cat results/SOD1_A4V/papers/papers.json | python -c "import json,sys; [print(f'{p[\"first_author\"]} ({p[\"publication_year\"]}) - {p[\"title\"]}') for p in json.load(sys.stdin)]"
```

### What each file contains

| File | What's in it | When to look at it |
|------|-------------|-------------------|
| **summary.md** | Full research summary with citations, clinical context, and therapeutic hypotheses | This is the main output — start here |
| **metadata.json** | Everything in machine-readable format: protein info, pLDDT scores, RMSD, ClinVar classification, gnomAD frequency, citations used | When you want to process results programmatically |
| **structure/*.pdb** | 3D protein structures you can open in PyMOL, ChimeraX, or any molecular viewer | When you want to visualize the structure |
| **visualizations/*plddt.png** | Per-residue confidence plot showing which parts of the structure are reliable | Quick visual check of prediction quality |
| **visualizations/*pae.png** | Predicted aligned error — shows which domain-domain relationships are confident | Understanding multi-domain proteins |
| **visualizations/*coverage.png** | How many homologous sequences were found for each region | Understanding prediction input quality |
| **analysis/confidence.json** | Numerical pLDDT scores, destabilized regions with residue ranges | Programmatic analysis of confidence |
| **analysis/rmsd.json** | RMSD values comparing your variant to wild-type | Quantifying structural deviation |
| **papers/papers.json** | Full PubMed results with titles, abstracts, DOIs, authors | Finding source papers, further reading |

### Example summary.md

```markdown
SOD1 (Superoxide dismutase) is a critical enzyme that protects cells from
oxidative damage. The A4V variant is the most common cause of familial ALS
(Lou Gehrig's disease) in North America, making its structural characterization
essential for understanding disease mechanisms.

---

The predicted structure of SOD1 A4V was generated using ColabFold (AlphaFold2)
and shows an average pLDDT confidence score of 82.4, indicating high overall
prediction reliability. The confidence distribution reveals 89 residues (58%)
in the very high confidence range (pLDDT > 90), with a destabilized region
spanning residues 37-42 (avg pLDDT: 61.3) near the dimer interface [1].

Structural comparison to the wild-type SOD1 (UniProt P00441) reveals an RMSD
of 1.87 A after alignment across 153 CA atoms, suggesting moderate
conformational changes introduced by the A4V substitution. The alanine-to-valine
change at position 4 disrupts hydrophobic packing in the beta-barrel core,
consistent with experimental findings showing destabilized dimer formation [2].

ClinVar classifies SOD1 A4V as "Pathogenic" with review by multiple
submitters, and the variant is absent from the gnomAD population database —
consistent with a rare, disease-causing mutation rather than benign
polymorphism. This clinical evidence aligns with the structural disruption
observed in the prediction.

Recent structural studies confirm that A4V promotes SOD1 monomerization,
a critical step in the aggregation pathway implicated in ALS pathology [3].
The low-confidence region at residues 37-42 overlaps with the electrostatic
loop, a region known to undergo conformational changes upon metal loss.
These findings suggest that small molecules stabilizing the dimer interface
could be a viable therapeutic strategy for A4V-linked ALS.

## Works Cited

[1] Grad et al. (2024). Mutant SOD1 structural dynamics in ALS.
Journal of Biological Chemistry. [PubMed](https://pubmed.ncbi.nlm.nih.gov/...)
[DOI](https://doi.org/10.1074/jbc...)
*Relevance: Demonstrates SOD1 A4V destabilizes dimer interface*

[2] Sheng et al. (2023). Crystal structure of A4V SOD1 variant.
Nature Structural Biology. [PubMed](https://pubmed.ncbi.nlm.nih.gov/...)
[DOI](https://doi.org/10.1038/...)
*Relevance: Experimental RMSD comparison for A4V substitution*

[3] Abel et al. (2024). SOD1 misfolding and aggregation in ALS.
Neuron. [PubMed](https://pubmed.ncbi.nlm.nih.gov/...)
[DOI](https://doi.org/10.1016/j.neuron...)
*Relevance: Links SOD1 monomerization to disease mechanism*

## Similar Research

- Wright et al. (2023). Copper-zinc superoxide dismutase variants...
  [PubMed](https://pubmed.ncbi.nlm.nih.gov/...)
- Danielsson et al. (2024). Aggregation propensity of SOD1 mutants...
  [PubMed](https://pubmed.ncbi.nlm.nih.gov/...)

---

*Generated by [fold-at-home](https://github.com/clarityprotocol/fold-at-home)*
```

## Configuration reference

Config file: `~/.fold-at-home/config.toml`

### [folding]

| Field | Default | Description |
|-------|---------|-------------|
| `backend` | `"colabfold"` | Folding backend: `"colabfold"` or `"alphafold"` |
| `colabfold_path` | `"colabfold_batch"` | Path to ColabFold binary. If it's in your PATH, just the name works. Otherwise use full path like `"/home/user/colabfold/bin/colabfold_batch"` |
| `alphafold_path` | `""` | Path to AlphaFold binary (only needed if backend is `"alphafold"`) |
| `gpu_device` | `""` | GPU to use. Empty = auto-detect. Set to `"0"` or `"1"` for multi-GPU systems |
| `timeout_hours` | `4.0` | Maximum hours per fold before timeout. Most proteins finish in 10-60 min. Increase for very large proteins (>1000 residues) |
| `num_models` | `5` | Number of models to predict. More = better quality but slower. Automatically reduced to 3 for large proteins |
| `memory_watchdog` | `true` | Monitor RAM during folds. Kills the fold process if your system runs low on memory (prevents freezes). Recommended on |

### [ai]

| Field | Default | Description |
|-------|---------|-------------|
| `provider` | `"anthropic"` | AI provider: `"anthropic"`, `"openai"`, or `"ollama"` |
| `model` | `""` | Model override. Empty = provider default (Claude Sonnet 4.5 for Anthropic, GPT-4o for OpenAI) |
| `anthropic_api_key` | `""` | Anthropic API key. Get one at [console.anthropic.com](https://console.anthropic.com). Or set `ANTHROPIC_API_KEY` env var instead |
| `openai_api_key` | `""` | OpenAI API key. Get one at [platform.openai.com](https://platform.openai.com). Or set `OPENAI_API_KEY` env var instead |
| `ollama_url` | `"http://localhost:11434"` | Ollama server URL. Only used when provider is `"ollama"` |
| `ollama_model` | `"llama3.1:70b"` | Ollama model name. Run `ollama list` to see installed models. The 70b model needs ~40 GB VRAM; use `"llama3.1:8b"` for smaller GPUs |

### [pubmed]

| Field | Default | Description |
|-------|---------|-------------|
| `email` | `"user@example.com"` | Your email address. **Required by NCBI** for PubMed API access. They use it to contact you if your usage causes problems. Use a real email |
| `ncbi_api_key` | `""` | Optional NCBI API key. Without it: 3 requests/sec. With it: 10 requests/sec. Free at [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/) |
| `max_papers` | `20` | Maximum papers to fetch per fold. More papers = more context for the AI but slower |

### [output]

| Field | Default | Description |
|-------|---------|-------------|
| `results_dir` | `"./results"` | Where to write fold results. Each fold gets a subdirectory (e.g., `results/SOD1_A4V/`) |

### [watch]

| Field | Default | Description |
|-------|---------|-------------|
| `poll_interval` | `60` | How often (seconds) to check the watch folder for new .fasta files |
| `archive_processed` | `true` | After processing, move .fasta to `archive/` subfolder. Set to `false` to leave files in place (creates `.done` marker instead) |

## AI providers

| Provider | Default Model | API Key Required | Cost | Notes |
|----------|--------------|-----------------|------|-------|
| Anthropic | Claude Sonnet 4.5 | Yes | ~$0.01-0.05/summary | Best quality summaries. Recommended |
| OpenAI | GPT-4o | Yes | ~$0.01-0.05/summary | Good alternative |
| Ollama | llama3.1:70b | No | Free (runs locally) | Quality varies by model. Needs powerful GPU |

**Env var alternative:** Instead of putting API keys in the config file, you can set environment variables:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

## External data sources

fold-at-home queries several public scientific databases during a fold. All are free and most require no account.

| Database | What it provides | Account needed? | Config |
|----------|-----------------|-----------------|--------|
| **UniProt** | Protein info, gene symbol, disease links, FASTA sequences | No | None |
| **AlphaFold DB** | Wild-type predicted structures (for RMSD comparison) | No | None |
| **PubMed** | Research papers with abstracts | Email required by NCBI | `[pubmed] email` |
| **ClinVar** | Variant pathogenicity classification (Pathogenic/Benign/VUS) | No (uses same NCBI email as PubMed) | Same as PubMed |
| **gnomAD** | Population allele frequency (how common is this variant?) | No | None |

### How each source is used

**UniProt** ([uniprot.org](https://www.uniprot.org/)) — When you provide a protein name, fold-at-home searches UniProt for the human entry. This gives us the canonical sequence (FASTA), the gene symbol, and any known disease associations. No API key needed.

**AlphaFold DB** ([alphafold.ebi.ac.uk](https://alphafold.ebi.ac.uk/)) — After folding your variant, we download the wild-type predicted structure from DeepMind's AlphaFold Protein Structure Database. This lets us compute RMSD (how much the variant structure deviates from normal). No account needed.

**PubMed** ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/)) — We search for papers about your protein and variant using NCBI's Entrez API. Abstracts are included in the AI prompt so the summary can cite real research. NCBI requires a valid email address (set in config). Optionally get a free API key at [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/) to increase rate limits from 3 to 10 requests/second.

**ClinVar** ([ncbi.nlm.nih.gov/clinvar](https://www.ncbi.nlm.nih.gov/clinvar/)) — A free NCBI database of variant-disease relationships. When you fold a variant, fold-at-home checks if it has a ClinVar entry and reports the clinical classification (e.g., "Pathogenic", "Likely pathogenic", "Uncertain significance", "Benign"). Uses the same NCBI email/key as PubMed — no extra setup needed.

**gnomAD** ([gnomad.broadinstitute.org](https://gnomad.broadinstitute.org/)) — The Genome Aggregation Database provides population-level allele frequencies from ~800,000 individuals. If your variant appears in gnomAD, we report how common it is in the general population. If it's absent, that's a signal it may be rare/pathogenic. Completely free, no account or API key needed.

### What this means for your summary

When clinical data is available, the AI integrates it into the summary:
- **ClinVar "Pathogenic"** + **absent from gnomAD** = strong evidence for disease-causing variant
- **ClinVar "Benign"** + **common in gnomAD** = likely normal population variation
- **No ClinVar entry** = variant hasn't been clinically evaluated yet (the summary notes this)

## Memory safety

fold-at-home includes memory protection to prevent system freezes during large folds:

- **Preflight checks** — verifies at least 16 GB RAM available before starting. Won't launch if memory is too low
- **Memory watchdog** — background thread monitors RAM every 5 seconds. If available memory drops below 4 GB, kills the fold process before your system freezes
- **Large protein detection** — proteins over 1000 residues automatically use fewer models (3 instead of 5) and reduced MSA depth to lower memory usage
- **Stale process cleanup** — detects and kills orphaned ColabFold processes from previous crashes

## Troubleshooting

### `colabfold_batch: command not found`
ColabFold isn't in your PATH. Either:
- Activate the conda environment: `conda activate colabfold`
- Set the full path in config: `colabfold_path = "/home/you/miniconda3/envs/colabfold/bin/colabfold_batch"`

### `CUDA out of memory`
Your GPU doesn't have enough VRAM for this protein. Try:
- Reduce models: set `num_models = 3` in config
- The tool automatically reduces settings for proteins >1000 residues, but some medium-sized proteins can also be memory-intensive

### `No API key` in status
Set your API key in the config file or as an environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

### `PubMed search failed`
Usually a network issue. The tool will still complete — papers are optional. Use `--skip-papers` to skip entirely.

### Fold takes too long
ColabFold runtime depends on protein size:
- Small proteins (<200 residues): 5-15 minutes
- Medium (200-500): 15-45 minutes
- Large (500-1000): 45-120 minutes
- Very large (>1000): 2-4+ hours

If a fold exceeds `timeout_hours`, it's killed automatically.

### System freezes during fold
Enable the memory watchdog (on by default): `memory_watchdog = true`. If freezes persist, reduce `num_models` to 3 and check your system has at least 16 GB RAM.

## License

MIT

## Credits

Built on [ColabFold](https://github.com/sokrypton/ColabFold), [AlphaFold](https://github.com/google-deepmind/alphafold), [BioPython](https://biopython.org/), [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/), [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/), and [gnomAD](https://gnomad.broadinstitute.org/).

Part of the [Clarity Protocol](https://clarityprotocol.io) ecosystem.
