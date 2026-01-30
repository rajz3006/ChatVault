"""Config management for ChatVault — loads from YAML with env var overrides."""
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Any

import os
import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".chatvault"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"


@dataclass
class Config:
    """ChatVault configuration."""

    data_dir: str = "./data"
    db_path: str = "chatvault.db"
    chroma_dir: str = "chroma_data"
    llm_backend: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    anthropic_model: str = "claude-sonnet-4-20250514"

    def __post_init__(self) -> None:
        """Apply environment variable overrides."""
        env_map: dict[str, str] = {
            "ollama_host": "OLLAMA_HOST",
            "ollama_model": "OLLAMA_MODEL",
        }
        for field_name, env_var in env_map.items():
            val = os.environ.get(env_var)
            if val is not None:
                object.__setattr__(self, field_name, val)

        # If ANTHROPIC_API_KEY is set, it's available but not stored in config
        # (accessed directly via os.environ when needed)


def load_config(path: str | Path | None = None) -> Config:
    """Load config from YAML file, falling back to defaults.

    Args:
        path: Path to config YAML. Defaults to ~/.chatvault/config.yaml.

    Returns:
        Config instance with file values merged over defaults, then env overrides.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if config_path.exists():
        with open(config_path, "r") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        valid_fields = {fld.name for fld in fields(Config)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return Config(**filtered)

    return Config()


def save_config(config: Config, path: str | Path | None = None) -> Path:
    """Save config to YAML file.

    Args:
        config: Config instance to save.
        path: Destination path. Defaults to ~/.chatvault/config.yaml.

    Returns:
        The path the config was saved to.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(asdict(config), f, default_flow_style=False, sort_keys=False)

    return config_path
