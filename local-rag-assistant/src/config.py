"""
src/config.py
Load and validate config.yaml. All modules import from here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# ── Sub-models ────────────────────────────────────────────────────────────────


class PathsConfig(BaseModel):
    raw_data: str = "data/raw"
    processed: str = "data/processed"
    chroma_db: str = "db/chroma"
    sqlite_db: str = "db/events.db"


class ModelsConfig(BaseModel):
    # llm: str = "mistral-small3.2:latest"
    llm: str = "gemma4"
    embeddings: str = "mxbai-embed-large"


class ChunkingConfig(BaseModel):
    chunk_size: int = 600
    chunk_overlap: int = 80


class RetrievalConfig(BaseModel):
    top_k: int = 6
    bm25_weight: float = 0.3
    vector_weight: float = 0.7


class ExtractionConfig(BaseModel):
    batch_size: int = 5
    max_events_per_page: int = 10


class AppConfig(BaseModel):
    paths: PathsConfig = Field(default_factory=PathsConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)


# ── Loader ────────────────────────────────────────────────────────────────────


def _find_config() -> Path:
    """Walk up from cwd to find config.yaml."""
    here = Path(os.getcwd())
    for candidate in [here / "config.yaml", here.parent / "config.yaml"]:
        if candidate.exists():
            return candidate
    # Fall back to example so the project runs without manual setup
    example = here / "config.example.yaml"
    if example.exists():
        return example
    raise FileNotFoundError(
        "config.yaml not found. Copy config.example.yaml → config.yaml and edit it."
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path else _find_config()
    with config_path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}
    return AppConfig(**raw)


# ── Singleton for convenience ─────────────────────────────────────────────────
_cfg: AppConfig | None = None


def get_config() -> AppConfig:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg
