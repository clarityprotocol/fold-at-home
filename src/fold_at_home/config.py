"""Configuration loading and validation for fold-at-home."""

import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".fold-at-home"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class FoldingConfig(BaseModel):
    backend: str = "colabfold"
    colabfold_path: str = "colabfold_batch"
    alphafold_path: str = ""
    gpu_device: str = ""
    timeout_hours: float = 4.0
    num_models: int = 5
    memory_watchdog: bool = True


class AIConfig(BaseModel):
    provider: str = "anthropic"
    model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:70b"

    def get_api_key(self) -> Optional[str]:
        """Resolve API key from config or environment variable."""
        if self.provider == "anthropic":
            return self.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == "openai":
            return self.openai_api_key or os.getenv("OPENAI_API_KEY")
        return None


class PubMedConfig(BaseModel):
    email: str = "user@example.com"
    ncbi_api_key: str = ""
    max_papers: int = 20


class OutputConfig(BaseModel):
    results_dir: str = "./results"


class WatchConfig(BaseModel):
    poll_interval: int = 60
    archive_processed: bool = True


class Config(BaseModel):
    folding: FoldingConfig = Field(default_factory=FoldingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    pubmed: PubMedConfig = Field(default_factory=PubMedConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)


def load_config() -> Config:
    """Load config from TOML file, falling back to defaults."""
    if not CONFIG_FILE.exists():
        return Config()

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return Config()

    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)

    return Config(**data)


def create_default_config() -> Path:
    """Create config directory and default config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    example = Path(__file__).parent.parent.parent / "example_config.toml"
    if example.exists():
        import shutil
        shutil.copy(example, CONFIG_FILE)
    else:
        CONFIG_FILE.write_text(_DEFAULT_CONFIG)
    return CONFIG_FILE


_DEFAULT_CONFIG = """\
# fold-at-home configuration

[folding]
backend = "colabfold"
colabfold_path = "colabfold_batch"
gpu_device = ""
timeout_hours = 4.0
num_models = 5
memory_watchdog = true

[ai]
provider = "anthropic"
model = ""
anthropic_api_key = ""
openai_api_key = ""
ollama_url = "http://localhost:11434"
ollama_model = "llama3.1:70b"

[pubmed]
email = "user@example.com"
ncbi_api_key = ""
max_papers = 20

[output]
results_dir = "./results"

[watch]
poll_interval = 60
archive_processed = true
"""
