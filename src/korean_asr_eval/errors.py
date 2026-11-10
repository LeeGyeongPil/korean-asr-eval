"""Exceptions and warnings raised by korean-asr-eval."""

from __future__ import annotations


class KoreanAsrEvalError(Exception):
    """Base class of every error this library raises on purpose."""


class UnknownProfileError(KoreanAsrEvalError):
    """A profile id such as ``name@3`` is not registered."""


class ProfileFormatError(KoreanAsrEvalError):
    """A profile definition (TOML file or step parameters) is invalid."""


class InputFormatError(KoreanAsrEvalError):
    """A reference/hypothesis file or argument has an unusable shape."""


class IdMismatchError(KoreanAsrEvalError):
    """Reference and hypothesis utterance ids do not line up.

    Attributes:
        missing: ids present in the reference but absent from the hypothesis.
        extra: ids present in the hypothesis but absent from the reference.
    """

    def __init__(self, missing: list[str], extra: list[str], system: str | None = None):
        self.missing = list(missing)
        self.extra = list(extra)
        self.system = system
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} id(s) missing from hypothesis: {_preview(self.missing)}")
        if self.extra:
            parts.append(f"{len(self.extra)} id(s) not in reference: {_preview(self.extra)}")
        where = f" for system {system!r}" if system else ""
        super().__init__(
            "utterance ids do not match" + where + "; " + "; ".join(parts)
            + ". Fix the ids, or drop the extra lines from the hypothesis file."
        )


class EmptyReferenceWarning(UserWarning):
    """A reference became empty after normalization.

    Such utterances are counted in ``Score.empty_refs``, excluded from the macro
    average, and their hypothesis characters count as insertions in the micro rate.
    """


def _preview(items: list[str], limit: int = 10) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f", ... (+{len(items) - limit} more)" if len(items) > limit else "")
