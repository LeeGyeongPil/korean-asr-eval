"""Apply a profile to text."""

from __future__ import annotations

from dataclasses import dataclass

from .profiles import Profile, resolve_profile


@dataclass(frozen=True)
class TraceStep:
    """Text before and after one step of a profile."""

    step: str
    before: str
    after: str


def normalize(text: str, profile: str | Profile = "basic@1") -> str:
    """Normalize ``text`` with ``profile`` (a built-in id, a ``.toml`` path or a Profile)."""
    p = resolve_profile(profile)
    for step in p.steps:
        text = step.apply(text)
    return text


def normalize_trace(text: str, profile: str | Profile = "basic@1") -> list[TraceStep]:
    """Like :func:`normalize` but returns the text before/after every step."""
    p = resolve_profile(profile)
    trace: list[TraceStep] = []
    for step in p.steps:
        after = step.apply(text)
        trace.append(TraceStep(step.label, text, after))
        text = after
    return trace
