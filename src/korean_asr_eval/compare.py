"""Compare several systems under several profiles: how much does the scoring
rule move the numbers and the ranking?"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import _version
from .errors import InputFormatError
from .profiles import Profile, resolve_profile
from .scoring import Score, TextSet, _as_aligned, _r, score

DEFAULT_PROFILES = ("none@1", "kspon-spelling@1", "kspon-phonetic@1")
_EPS = 1e-12


@dataclass(frozen=True)
class RankFlip:
    """Two systems whose order differs between two profiles.

    ``pair`` is the two system names sorted alphabetically.
    """

    pair: tuple[str, str]
    profile_a: str
    profile_b: str
    ahead_in_a: str
    ahead_in_b: str


@dataclass(frozen=True)
class UttChange:
    """One utterance whose CER moved between the first and last profile."""

    id: str
    profile_from: str
    profile_to: str
    cer_from: float
    cer_to: float
    delta_pp: float
    ref: str
    hyp: str


@dataclass(frozen=True)
class Comparison:
    """Result of :func:`compare`.

    Attributes:
        profiles: profile ids in the order given (the first is the baseline).
        systems: system names in the order given.
        table: ``table[system][profile_id]`` is a :class:`Score`.
        ranks: per profile id, system names best (lowest CER) first; ties by name.
        deltas_pp: CER change versus the baseline profile, in percentage points.
        rank_flips: pairs of systems ordered differently under two profiles.
        top_changed: per system, utterances whose CER changed most between the
            first and the last profile (largest absolute change first).
    """

    profiles: list[str]
    fingerprints: dict[str, str]
    systems: list[str]
    table: dict[str, dict[str, Score]]
    ranks: dict[str, list[str]]
    deltas_pp: dict[str, dict[str, float | None]]
    rank_flips: list[RankFlip]
    top_changed: dict[str, list[UttChange]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict (rates rounded to 4 decimals, no timestamps or paths)."""
        return {
            "korean_asr_eval_version": _version.package_version(),
            "jiwer_version": _version.jiwer_version(),
            "profiles": [{"id": p, "fingerprint": self.fingerprints[p]} for p in self.profiles],
            "systems": list(self.systems),
            "table": {
                s: {p: self.table[s][p].to_dict(include_utterances=False) for p in self.profiles}
                for s in self.systems
            },
            "ranks": {p: list(self.ranks[p]) for p in self.profiles},
            "deltas_pp": {
                s: {p: _r(self.deltas_pp[s][p]) for p in self.profiles} for s in self.systems
            },
            "rank_flips": [
                {
                    "pair": list(f.pair),
                    "profile_a": f.profile_a,
                    "profile_b": f.profile_b,
                    "ahead_in_a": f.ahead_in_a,
                    "ahead_in_b": f.ahead_in_b,
                }
                for f in self.rank_flips
            ],
            "top_changed": {
                s: [
                    {
                        "id": c.id,
                        "profile_from": c.profile_from,
                        "profile_to": c.profile_to,
                        "cer_from": _r(c.cer_from),
                        "cer_to": _r(c.cer_to),
                        "delta_pp": _r(c.delta_pp),
                        "ref": c.ref,
                        "hyp": c.hyp,
                    }
                    for c in self.top_changed.get(s, [])
                ]
                for s in self.systems
            },
        }

    def to_markdown(self) -> str:
        from .report import comparison_markdown

        return comparison_markdown(self)

    def to_text(self) -> str:
        from .report import comparison_text

        return comparison_text(self)


def _key(value: float | None) -> float:
    return math.inf if value is None else value


def compare(
    refs: TextSet,
    systems: Mapping[str, TextSet],
    profiles: Sequence[str | Profile] = DEFAULT_PROFILES,
    *,
    top_n: int = 5,
) -> Comparison:
    """Score every system under every profile and report what the profile changes.

    Args:
        refs: reference transcripts (list or ``{id: text}``).
        systems: ``{system_name: hypotheses}``; same shape as ``refs``.
        profiles: profile ids / ``.toml`` paths / Profiles; the first is the baseline.
        top_n: how many most-changed utterances to keep per system.

    Raises:
        InputFormatError: no systems or profiles, or duplicate profile ids.
        IdMismatchError: a system's ids differ from the reference ids.
    """
    if not systems:
        raise InputFormatError("compare needs at least one system, e.g. systems={'a': hyps}")
    resolved = [resolve_profile(p) for p in profiles]
    if not resolved:
        raise InputFormatError("compare needs at least one profile")
    ids = [p.id for p in resolved]
    if len(set(ids)) != len(ids):
        raise InputFormatError(f"duplicate profile ids in compare: {', '.join(ids)}")

    names = list(systems)
    table: dict[str, dict[str, Score]] = {}
    aligned: dict[str, tuple[list[str], list[str], list[str]]] = {}
    for name in names:
        aligned[name] = _as_aligned(refs, systems[name], None, name)
        _, r, h = aligned[name]
        table[name] = {p.id: score(r, h, p, ids=aligned[name][0], system=name) for p in resolved}

    ranks = {
        pid: sorted(names, key=lambda s, pid=pid: (_key(table[s][pid].cer), s)) for pid in ids
    }
    base = ids[0]
    deltas: dict[str, dict[str, float | None]] = {}
    for s in names:
        b = table[s][base].cer
        deltas[s] = {
            pid: None if b is None or table[s][pid].cer is None else (table[s][pid].cer - b) * 100
            for pid in ids
        }

    flips: list[RankFlip] = []
    ordered = sorted(names)
    for i, pa in enumerate(ids):
        for pb in ids[i + 1:]:
            for x_i, x in enumerate(ordered):
                for y in ordered[x_i + 1:]:
                    da = _key(table[x][pa].cer) - _key(table[y][pa].cer)
                    db = _key(table[x][pb].cer) - _key(table[y][pb].cer)
                    if (
                        not (math.isnan(da) or math.isnan(db))
                        and abs(da) > _EPS and abs(db) > _EPS and da * db < 0
                    ):
                        flips.append(
                            RankFlip((x, y), pa, pb, x if da < 0 else y, x if db < 0 else y)
                        )

    top: dict[str, list[UttChange]] = {s: [] for s in names}
    if len(ids) > 1:
        last = ids[-1]
        for s in names:
            uid_list, r_list, h_list = aligned[s]
            changes: list[UttChange] = []
            for k, uid in enumerate(uid_list):
                a = table[s][base].utterances[k].cer
                b = table[s][last].utterances[k].cer
                if a is None or b is None or abs(b - a) < _EPS:
                    continue
                changes.append(
                    UttChange(uid, base, last, a, b, (b - a) * 100, r_list[k], h_list[k])
                )
            changes.sort(key=lambda c: (-abs(c.delta_pp), c.id))
            top[s] = changes[: max(top_n, 0)]

    return Comparison(
        profiles=ids,
        fingerprints={p.id: p.fingerprint for p in resolved},
        systems=names,
        table=table,
        ranks=ranks,
        deltas_pp=deltas,
        rank_flips=flips,
        top_changed=top,
    )
