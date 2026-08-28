"""Approximate token counting for exported calibration files.

No tokenizer library is a dependency of this project (tiktoken isn't
installed — checked before writing this rather than adding a new
dependency for one heuristic). The chars/4 approximation is the standard
rule of thumb for English/Ukrainian-mixed prose with an OpenAI-family
tokenizer and is what this is calibrated against — it's an estimate, not
an exact count, and is labeled as such everywhere it's surfaced (the
exported files' own metadata and calibration_report.md).
"""

from __future__ import annotations

_CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str) -> int:
    return round(len(text) / _CHARS_PER_TOKEN)
