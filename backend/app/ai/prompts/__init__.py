"""Carregamento dos prompts versionados (cabeçalho com `prompt_version`)."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str


@cache
def load_prompt(name: str) -> Prompt:
    raw = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---\n"):
        header, _, body = raw[4:].partition("\n---\n")
        for line in header.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                meta[key.strip()] = value.strip()
    if "prompt_version" not in meta:
        raise ValueError(f"Prompt {name}.md sem prompt_version no cabeçalho")
    return Prompt(name=name, version=meta["prompt_version"], text=body.strip())
