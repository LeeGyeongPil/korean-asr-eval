"""Human-readable and JSON renderings of results.

JSON output uses sorted keys and contains no timestamps or absolute paths, so the
same input always yields the same bytes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid an import cycle at runtime
    from .compare import Comparison
    from .scoring import Score


def to_json(obj: dict[str, Any]) -> str:
    """Deterministic JSON text (sorted keys, UTF-8 friendly, trailing newline)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def score_text(s: Score) -> str:
    lines = [
        f"profile: {s.profile_id} (fp {s.fingerprint})",
        f"utterances: {s.n_utts}  reference chars: {s.ref_chars}  empty refs: {s.empty_refs}",
        f"CER         {_fmt(s.cer)}   (micro, spaces count as characters)",
        f"CER-nospace {_fmt(s.cer_nospace)}   (spaces ignored)",
        f"CER-macro   {_fmt(s.cer_macro)}   (mean of per-utterance CER)",
        f"WER         {_fmt(s.wer)}   (space-separated words)",
        f"S/D/I/H     {s.substitutions}/{s.deletions}/{s.insertions}/{s.hits}   (characters)",
    ]
    return "\n".join(lines) + "\n"


def score_markdown(s: Score) -> str:
    rows = [
        ("profile", f"`{s.profile_id}` (fp `{s.fingerprint}`)"),
        ("utterances", str(s.n_utts)),
        ("empty refs", str(s.empty_refs)),
        ("CER", _fmt(s.cer)),
        ("CER-nospace", _fmt(s.cer_nospace)),
        ("CER-macro", _fmt(s.cer_macro)),
        ("WER", _fmt(s.wer)),
        ("S/D/I/H (chars)", f"{s.substitutions}/{s.deletions}/{s.insertions}/{s.hits}"),
    ]
    out = ["| metric | value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(out) + "\n"


def _cell(c: Comparison, system: str, pid: str) -> str:
    cer = c.table[system][pid].cer
    delta = c.deltas_pp[system][pid]
    if pid == c.profiles[0] or delta is None:
        return _fmt(cer)
    return f"{_fmt(cer)} ({delta:+.1f}pp)"


def _flip_line(f: Any) -> str:
    return (
        f"rank flip: {f.pair[0]} vs {f.pair[1]} - {f.ahead_in_a} ahead under {f.profile_a}, "
        f"{f.ahead_in_b} ahead under {f.profile_b}"
    )


def comparison_text(c: Comparison) -> str:
    head = ["system"] + c.profiles
    rows = [[s] + [_cell(c, s, p) for p in c.profiles] for s in c.systems]
    widths = [max(len(r[i]) for r in [head] + rows) for i in range(len(head))]

    def line(cells: list[str]) -> str:
        return "  ".join(x.ljust(w) for x, w in zip(cells, widths)).rstrip()

    out = [f"CER by profile (micro, lower is better; pp = change versus {c.profiles[0]})"]
    out.append(line(head))
    out += [line(r) for r in rows]
    out.append("")
    out.append("profile fingerprints: " + ", ".join(f"{p}={c.fingerprints[p]}" for p in c.profiles))
    out.append("ranking (best first):")
    out += [f"  {p}: " + " < ".join(c.ranks[p]) for p in c.profiles]
    out.append("")
    if c.rank_flips:
        out += [_flip_line(f) for f in c.rank_flips]
    else:
        out.append("no rank flips: the ranking is the same under every profile")
    shown = {s: ch for s, ch in c.top_changed.items() if ch}
    if shown:
        out.append("")
        out.append(f"most changed utterances ({c.profiles[0]} -> {c.profiles[-1]}):")
        for s, changes in shown.items():
            for ch in changes:
                out.append(
                    f"  {s} {ch.id}: {_fmt(ch.cer_from)} -> {_fmt(ch.cer_to)} ({ch.delta_pp:+.1f}pp)"
                )
                out.append(f"    ref: {ch.ref}")
                out.append(f"    hyp: {ch.hyp}")
    return "\n".join(out) + "\n"


def comparison_markdown(c: Comparison) -> str:
    out = [f"### CER by profile (micro; pp = change versus `{c.profiles[0]}`)", ""]
    out.append("| system | " + " | ".join(f"`{p}`" for p in c.profiles) + " |")
    out.append("|---|" + "---|" * len(c.profiles))
    for s in c.systems:
        out.append(f"| {s} | " + " | ".join(_cell(c, s, p) for p in c.profiles) + " |")
    out += ["", "### Ranking (best first)", ""]
    out += [f"- `{p}` (fp `{c.fingerprints[p]}`): " + " < ".join(c.ranks[p]) for p in c.profiles]
    out += ["", "### Rank flips", ""]
    if c.rank_flips:
        out += [f"- {_flip_line(f)}" for f in c.rank_flips]
    else:
        out.append("- none: the ranking is the same under every profile")
    shown = {s: ch for s, ch in c.top_changed.items() if ch}
    if shown:
        out += ["", f"### Most changed utterances (`{c.profiles[0]}` -> `{c.profiles[-1]}`)", ""]
        out += ["| system | id | CER from | CER to | change | reference | hypothesis |",
                "|---|---|---|---|---|---|---|"]
        for s, changes in shown.items():
            for ch in changes:
                ref = ch.ref.replace("|", "\\|")
                hyp = ch.hyp.replace("|", "\\|")
                out.append(
                    f"| {s} | {ch.id} | {_fmt(ch.cer_from)} | {_fmt(ch.cer_to)} | "
                    f"{ch.delta_pp:+.1f}pp | {ref} | {hyp} |"
                )
    return "\n".join(out) + "\n"
