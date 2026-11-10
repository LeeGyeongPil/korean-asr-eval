"""Version lookups recorded in every result (jiwer has no ``__version__``)."""

from __future__ import annotations

from importlib import metadata


def package_version() -> str:
    try:
        return metadata.version("korean-asr-eval")
    except metadata.PackageNotFoundError:  # running from a bare source tree
        return "0.0.0+unknown"


def jiwer_version() -> str:
    try:
        return metadata.version("jiwer")
    except metadata.PackageNotFoundError:
        return "unknown"
