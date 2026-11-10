"""Bridge to jiwer: export a profile as a ``jiwer.Compose`` and share the
transform chains that :func:`korean_asr_eval.score` itself uses, so the two
always agree."""

from __future__ import annotations

from jiwer import transforms as T

from .errors import KoreanAsrEvalError
from .normalize import normalize
from .profiles import Profile, resolve_profile


class ProfileTransform(T.AbstractTransform):
    """A jiwer transform that applies a normalization profile to each string."""

    def __init__(self, profile: Profile):
        self.profile = profile

    def process_string(self, s: str) -> str:
        return normalize(s, self.profile)


def tail_transforms(unit: str = "char", ignore_space: bool = False) -> list[T.AbstractTransform]:
    """The jiwer steps that follow normalization.

    They match jiwer's own ``cer_default`` / ``wer_default`` chains, with all
    whitespace removed first when ``ignore_space`` is set (characters only).
    """
    if unit == "char":
        if ignore_space:
            return [T.RemoveWhiteSpace(replace_by_space=False), T.ReduceToListOfListOfChars()]
        return [T.RemoveMultipleSpaces(), T.Strip(), T.ReduceToListOfListOfChars()]
    if unit == "word":
        if ignore_space:
            raise KoreanAsrEvalError("ignore_space only makes sense with unit='char'")
        return [T.RemoveMultipleSpaces(), T.Strip(), T.ReduceToListOfListOfWords()]
    raise KoreanAsrEvalError(f"unit must be 'char' or 'word', got {unit!r}")


def to_jiwer_transform(
    profile: str | Profile, unit: str = "char", ignore_space: bool = False
) -> T.Compose:
    """Export ``profile`` as a ``jiwer.Compose`` for jiwer's metric functions.

    Example::

        t = to_jiwer_transform("kspon-phonetic@1")
        jiwer.cer(refs, hyps, reference_transform=t, hypothesis_transform=t)

    Args:
        profile: built-in id, ``.toml`` path or :class:`Profile`.
        unit: ``"char"`` for ``jiwer.cer`` or ``"word"`` for ``jiwer.wer``.
        ignore_space: remove all whitespace before comparing characters.
    """
    return T.Compose([ProfileTransform(resolve_profile(profile)), *tail_transforms(unit, ignore_space)])


__all__ = ["ProfileTransform", "to_jiwer_transform", "tail_transforms"]
