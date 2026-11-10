"""Normalization steps: small pure functions looked up by name.

A *profile* (see :mod:`korean_asr_eval.profiles`) is an ordered list of these
steps. Every step takes the text as its first argument and keyword-only
parameters. Changing what a step does would silently change scores, so a
behaviour change here must come with a new profile version, never an edit of an
existing one.
"""

from __future__ import annotations

import inspect
import re
import unicodedata
from collections.abc import Callable, Mapping
from typing import Any

from .errors import ProfileFormatError

# "(spelling)/(pronunciation)" pair used by KsponSpeech transcripts.
_DUAL_RE = re.compile(r"\(([^()]*)\)/\(([^()]*)\)")
# Noise tags: b/ n/ o/ l/ u/ standing alone as a token.
_TAG_RE = re.compile(r"(?<!\S)[bnolu]/(?=\s|$)", re.IGNORECASE)


def nfc(text: str) -> str:
    """Unicode NFC. Decomposed (NFD) Hangul would otherwise inflate CER."""
    return unicodedata.normalize("NFC", text)


def strip(text: str) -> str:
    """Remove leading and trailing whitespace only."""
    return text.strip()


def lowercase(text: str) -> str:
    """Lowercase Latin letters (Hangul is unaffected)."""
    return text.lower()


def kspon_dual(text: str, *, choose: str = "spelling") -> str:
    """Resolve KsponSpeech ``(spelling)/(pronunciation)`` pairs.

    ``choose`` is ``"spelling"`` (first) or ``"phonetic"`` (second).
    """
    if choose not in ("spelling", "phonetic"):
        raise ProfileFormatError(
            f"kspon_dual: choose must be 'spelling' or 'phonetic', got {choose!r}"
        )
    group = 1 if choose == "spelling" else 2
    return _DUAL_RE.sub(lambda m: m.group(group), text)


def kspon_noise_tags(text: str) -> str:
    """Remove noise tags ``b/ n/ o/ l/ u/`` (breath, noise, overlap, laugh, unclear)."""
    return _TAG_RE.sub("", text)


def kspon_marks(text: str) -> str:
    """Remove disfluency / repetition / unclear marks ``/``, ``+`` and ``*``."""
    return text.replace("/", "").replace("+", "").replace("*", "")


def percent_word(text: str, *, word: str = "퍼센트") -> str:
    """Replace ``%`` with ``word`` (no surrounding spaces added)."""
    return text.replace("%", word)


def replace(text: str, *, pairs: list[list[str]] | None = None) -> str:
    """Apply literal replacements in the order given.

    ``pairs`` is a list of ``[old, new]`` lists. Order matters: later pairs see the
    output of earlier ones.
    """
    for old, new in pairs or []:
        text = text.replace(old, new)
    return text


def punct_to_space(text: str, *, keep: str = "") -> str:
    """Turn Unicode punctuation (P*) and symbols (S*) into spaces.

    Characters listed in ``keep`` are left alone.
    """
    return "".join(
        " " if unicodedata.category(c)[0] in "PS" and c not in keep else c for c in text
    )


def collapse_spaces(text: str) -> str:
    """Collapse runs of whitespace into one space and strip the ends."""
    return " ".join(text.split())


STEPS: dict[str, Callable[..., str]] = {
    f.__name__: f
    for f in (
        nfc,
        strip,
        lowercase,
        kspon_dual,
        kspon_noise_tags,
        kspon_marks,
        percent_word,
        replace,
        punct_to_space,
        collapse_spaces,
    )
}


def canonical_params(name: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """Validate ``params`` for step ``name`` and fill in defaults.

    Recording defaults explicitly keeps profile fingerprints stable even if a
    function's default is spelled out in one place and omitted in another.

    Raises:
        ProfileFormatError: unknown step, unknown/invalid parameter.
    """
    func = STEPS.get(name)
    if func is None:
        raise ProfileFormatError(f"unknown step {name!r}; available steps: {', '.join(STEPS)}")
    sig = inspect.signature(func)
    allowed = [p for p in list(sig.parameters)[1:]]
    unknown = [k for k in params if k not in allowed]
    if unknown:
        raise ProfileFormatError(
            f"step {name!r} has no parameter(s) {', '.join(map(repr, unknown))}; "
            f"allowed: {', '.join(allowed) or '(none)'}"
        )
    values: dict[str, Any] = {k: sig.parameters[k].default for k in allowed}
    values.update(params)
    if name == "replace":
        values["pairs"] = _canonical_pairs(values.get("pairs"))
    # Run once on an empty string so wrong parameter types/values fail early.
    try:
        func("", **values)
    except ProfileFormatError:
        raise
    except Exception as exc:  # noqa: BLE001 - re-raised with a fix hint
        raise ProfileFormatError(f"step {name!r} rejected its parameters: {exc}") from exc
    return values


def _canonical_pairs(raw: Any) -> list[list[str]]:
    """Accept a mapping or a list of 2-item lists; return NFC ``[old, new]`` lists."""
    if raw is None:
        return []
    items = list(raw.items()) if isinstance(raw, Mapping) else list(raw)
    pairs: list[list[str]] = []
    for item in items:
        if (
            not isinstance(item, (list, tuple))
            or len(item) != 2
            or not all(isinstance(x, str) for x in item)
        ):
            raise ProfileFormatError(
                "replace pairs must be a table of strings or a list of [old, new] string pairs"
            )
        old, new = item
        if old == "":
            raise ProfileFormatError("replace: an empty 'old' string is not allowed")
        pairs.append([nfc(old), nfc(new)])
    return pairs
