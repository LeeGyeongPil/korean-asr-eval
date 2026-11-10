"""Scoring: normalize both sides with one profile, then let jiwer count errors."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import jiwer

from . import _version
from .errors import EmptyReferenceWarning, InputFormatError
from .io import align
from .jiwer_compat import to_jiwer_transform
from .profiles import Profile, resolve_profile

TextSet = Sequence[str] | Mapping[str, str]


@dataclass(frozen=True)
class UttScore:
    """Per-utterance counts. ``cer`` is ``None`` when the reference is empty."""

    id: str
    cer: float | None
    cer_nospace: float | None
    wer: float | None
    substitutions: int
    deletions: int
    insertions: int
    hits: int
    ref_chars: int


@dataclass(frozen=True)
class Score:
    """Result of :func:`score`. Error counts are character-level (spaces count).

    ``cer`` / ``cer_nospace`` / ``wer`` are micro rates: total errors divided by
    total reference length. ``cer_macro`` is the mean of per-utterance CER over
    utterances whose normalized reference is not empty.
    """

    profile_id: str
    fingerprint: str
    n_utts: int
    ref_chars: int
    cer: float | None
    cer_nospace: float | None
    cer_macro: float | None
    wer: float | None
    substitutions: int
    deletions: int
    insertions: int
    hits: int
    empty_refs: int
    utterances: list[UttScore] = field(default_factory=list)

    def to_dict(self, include_utterances: bool = True) -> dict[str, Any]:
        """JSON-ready dict: rates rounded to 4 decimals, no timestamps or paths."""
        out: dict[str, Any] = {
            "profile_id": self.profile_id,
            "fingerprint": self.fingerprint,
            "korean_asr_eval_version": _version.package_version(),
            "jiwer_version": _version.jiwer_version(),
            "n_utts": self.n_utts,
            "ref_chars": self.ref_chars,
            "cer": _r(self.cer),
            "cer_nospace": _r(self.cer_nospace),
            "cer_macro": _r(self.cer_macro),
            "wer": _r(self.wer),
            "substitutions": self.substitutions,
            "deletions": self.deletions,
            "insertions": self.insertions,
            "hits": self.hits,
            "empty_refs": self.empty_refs,
        }
        if include_utterances:
            out["utterances"] = [
                {
                    "id": u.id,
                    "cer": _r(u.cer),
                    "cer_nospace": _r(u.cer_nospace),
                    "wer": _r(u.wer),
                    "substitutions": u.substitutions,
                    "deletions": u.deletions,
                    "insertions": u.insertions,
                    "hits": u.hits,
                    "ref_chars": u.ref_chars,
                }
                for u in self.utterances
            ]
        return out


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _as_aligned(
    refs: TextSet, hyps: TextSet, ids: Sequence[str] | None, system: str | None
) -> tuple[list[str], list[str], list[str]]:
    for name, val in (("refs", refs), ("hyps", hyps)):
        if isinstance(val, str):
            raise InputFormatError(f"{name} must be a list of strings or a dict, not a single str")
    if isinstance(refs, Mapping) and isinstance(hyps, Mapping):
        return align(refs, hyps, system)
    if isinstance(refs, Mapping) or isinstance(hyps, Mapping):
        raise InputFormatError("refs and hyps must both be dicts (matched by id) or both be lists")
    if len(refs) != len(hyps):
        raise InputFormatError(
            f"refs has {len(refs)} item(s) but hyps has {len(hyps)}; "
            "they must match one-to-one (or pass dicts keyed by id)"
        )
    if ids is None:
        ids = [str(i) for i in range(1, len(refs) + 1)]
    elif len(ids) != len(refs):
        raise InputFormatError(f"ids has {len(ids)} item(s) but refs has {len(refs)}")
    return list(ids), list(refs), list(hyps)


def score(
    refs: TextSet,
    hyps: TextSet,
    profile: str | Profile = "basic@1",
    *,
    ids: Sequence[str] | None = None,
    system: str | None = None,
) -> Score:
    """Score ``hyps`` against ``refs`` after normalizing both with ``profile``.

    Args:
        refs, hyps: lists of strings (matched by position) or dicts keyed by
            utterance id (matched by id).
        profile: built-in id, ``.toml`` path or :class:`Profile`.
        ids: names for list inputs (default ``"1"``, ``"2"``, ...).
        system: label used in error messages.

    Raises:
        IdMismatchError: dict inputs whose ids differ.
        InputFormatError: list inputs of different length, or a bare string.

    Warns:
        EmptyReferenceWarning: a reference is empty after normalization.
    """
    prof = resolve_profile(profile)
    id_list, ref_list, hyp_list = _as_aligned(refs, hyps, ids, system)

    t_char = to_jiwer_transform(prof, "char")
    t_nospace = to_jiwer_transform(prof, "char", ignore_space=True)
    t_word = to_jiwer_transform(prof, "word")

    def run_chars(r: list[str], h: list[str], t: Any) -> Any:
        return jiwer.process_characters(r, h, reference_transform=t, hypothesis_transform=t)

    def run_words(r: list[str], h: list[str]) -> Any:
        return jiwer.process_words(r, h, reference_transform=t_word, hypothesis_transform=t_word)

    utts: list[UttScore] = []
    for uid, r, h in zip(id_list, ref_list, hyp_list):
        c = run_chars([r], [h], t_char)
        ns = run_chars([r], [h], t_nospace)
        w = run_words([r], [h])
        ref_chars = c.substitutions + c.deletions + c.hits
        ref_words = w.substitutions + w.deletions + w.hits
        empty = ref_chars == 0
        utts.append(
            UttScore(
                id=uid,
                cer=None if empty else c.cer,
                cer_nospace=None if ns.substitutions + ns.deletions + ns.hits == 0 else ns.cer,
                wer=None if ref_words == 0 else w.wer,
                substitutions=c.substitutions,
                deletions=c.deletions,
                insertions=c.insertions,
                hits=c.hits,
                ref_chars=ref_chars,
            )
        )

    empty_refs = sum(1 for u in utts if u.ref_chars == 0)
    if empty_refs:
        warnings.warn(
            f"{empty_refs} reference(s) are empty after normalizing with {prof.id}; "
            "they are excluded from the macro CER and their hypothesis characters count as "
            "insertions in the micro rates",
            EmptyReferenceWarning,
            stacklevel=2,
        )

    total_chars = sum(u.ref_chars for u in utts)
    macro_values = [u.cer for u in utts if u.cer is not None]

    cer = cer_nospace = wer = None
    if utts and total_chars > 0:
        # Micro rates come straight from jiwer over the whole corpus.
        cer = run_chars(ref_list, hyp_list, t_char).cer
        cer_nospace = run_chars(ref_list, hyp_list, t_nospace).cer
    if utts:
        words = run_words(ref_list, hyp_list)
        if words.substitutions + words.deletions + words.hits > 0:
            wer = words.wer

    return Score(
        profile_id=prof.id,
        fingerprint=prof.fingerprint,
        n_utts=len(utts),
        ref_chars=total_chars,
        cer=cer,
        cer_nospace=cer_nospace,
        cer_macro=(sum(macro_values) / len(macro_values)) if macro_values else None,
        wer=wer,
        substitutions=sum(u.substitutions for u in utts),
        deletions=sum(u.deletions for u in utts),
        insertions=sum(u.insertions for u in utts),
        hits=sum(u.hits for u in utts),
        empty_refs=empty_refs,
        utterances=utts,
    )
