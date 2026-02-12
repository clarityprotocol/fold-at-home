# fold-at-home

Predict protein structures and generate AI-powered research summaries — locally, on your own hardware.

## What it does

1. **Looks up your protein** in UniProt (or uses your FASTA file)
2. **Folds it** via ColabFold or AlphaFold
3. **Analyzes the structure** — pLDDT confidence scores, RMSD vs wild-type
4. **Finds relevant papers** on PubMed
5. **Generates a citation-backed summary** using Claude, GPT-4, or a local Ollama model
6. **Writes everything** to a clean results folder

## Install

```bash
pip install fold-at-home

# With AI provider support:
pip install "fold-at-home[anthropic]"   # Claude
pip install "fold-at-home[openai]"      # GPT-4
pip install "fold-at-home[all]"         # Both
```

### Prerequisites

- **ColabFold** or **AlphaFold** installed locally
  - [ColabFold install guide](https://github.com/sokrypton/ColabFold)
  - [AlphaFold install guide](https://github.com/google-deepmind/alphafold)
- **Python 3.10+**
- **GPU recommended** (ColabFold/AlphaFold are compute-intensive)

## Quick start

```bash
# Create config file
fold-at-home init

# Edit config with your API keys
nano ~/.fold-at-home/config.toml

# Check setup
fold-at-home status

# Fold a protein variant
fold-at-home fold SOD1 A4V

# Fold with a rationale
fold-at-home fold SOD1 A4V --rationale "ALS-linked variant"

# Use your own FASTA file
fold-at-home fold --fasta ~/my_protein.fasta --protein SOD1 --variant A4V
```

## Watch mode

Drop `.fasta` files into a folder and fold-at-home processes them automatically:

```bash
fold-at-home watch ~/my_folds/

# Custom poll interval
fold-at-home watch ~/my_folds/ --interval 30
```

### FASTA naming convention

The filename tells fold-at-home what it's folding:

```
SOD1_A4V.fasta         → protein=SOD1, variant=A4V
01_tau_P301L.fasta     → protein=tau, variant=P301L (number prefix for ordering)
alpha-synuclein.fasta  → protein=alpha-synuclein, no variant
```

## Output

Each fold produces a results directory:

```
results/SOD1_A4V/
├── structure/          # PDB files from folding
├── analysis/           # confidence.json, rmsd.json
├── visualizations/     # PNG plots (if generated)
├── papers/             # papers.json (PubMed data)
├── summary.md          # Human-readable research summary
└── metadata.json       # All structured data
```

### summary.md format

The summary includes:
- **TLDR** — 2-3 sentence plain-language summary
- **Detailed analysis** — structural findings with inline citations [1], [2]
- **Works Cited** — papers referenced in the summary with PubMed links
- **Similar Research** — related papers for further reading

## Configuration

Config lives at `~/.fold-at-home/config.toml`:

```toml
[folding]
backend = "colabfold"              # "colabfold" or "alphafold"
colabfold_path = "colabfold_batch" # Path to binary
gpu_device = ""                    # GPU device (empty = auto)
num_models = 5                     # Models to predict (3 for large proteins)
memory_watchdog = true             # Kill fold if memory runs low

[ai]
provider = "anthropic"             # "anthropic", "openai", or "ollama"
anthropic_api_key = ""             # Or set ANTHROPIC_API_KEY env var
openai_api_key = ""                # Or set OPENAI_API_KEY env var
ollama_url = "http://localhost:11434"
ollama_model = "llama3.1:70b"

[pubmed]
email = "your@email.com"           # Required by NCBI
ncbi_api_key = ""                  # Optional, enables faster searches
max_papers = 20

[output]
results_dir = "./results"

[watch]
poll_interval = 60                 # Seconds between queue checks
archive_processed = true           # Move processed FASTA to archive/
```

## Skip steps

Run only the parts you need:

```bash
# Already folded? Just analyze and summarize
fold-at-home fold SOD1 A4V --skip-fold

# No AI key? Skip the summary
fold-at-home fold SOD1 A4V --skip-summary

# Offline? Skip paper search
fold-at-home fold SOD1 A4V --skip-papers
```

## AI providers

| Provider | Model | Needs API key | Notes |
|----------|-------|---------------|-------|
| Anthropic | Claude Sonnet 4.5 | Yes | Best quality summaries |
| OpenAI | GPT-4o | Yes | Good alternative |
| Ollama | Any local model | No | Free, runs locally, quality varies |

## Memory safety

fold-at-home includes memory protection for large proteins:

- **Preflight checks** — won't start a fold if RAM is too low
- **Memory watchdog** — monitors RAM during folds, kills the process before your system freezes
- **Large protein detection** — automatically reduces models/MSA for proteins >1000 residues
- **Stale process cleanup** — kills orphaned ColabFold processes

## License

MIT

## Credits

Built on [ColabFold](https://github.com/sokrypton/ColabFold), [AlphaFold](https://github.com/google-deepmind/alphafold), [BioPython](https://biopython.org/), and the [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/).

Part of the [Clarity Protocol](https://clarityprotocol.io) ecosystem.
