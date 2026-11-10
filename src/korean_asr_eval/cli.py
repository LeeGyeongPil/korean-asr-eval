"""Command line interface: profiles, normalize, score, compare, demo.

Exit codes: 0 success, 2 for bad input (unknown profile, id mismatch, unreadable
file, malformed line, bad arguments).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from . import __version__
from .compare import DEFAULT_PROFILES, Comparison, compare
from .errors import EmptyReferenceWarning, InputFormatError, KoreanAsrEvalError
from .io import FORMATS, read_pairs
from .normalize import normalize, normalize_trace
from .profiles import list_profiles, load_profile, resolve_profile
from .report import comparison_markdown, comparison_text, score_markdown, score_text, to_json
from .scoring import score

DEMO_BANNER = (
    "[연습용 합성 샘플 / practice mock data] hand-written text in KsponSpeech style, "
    "NOT real model output. model-a/b/c are imaginary systems; the arithmetic is real (jiwer)."
)
DEMO_SYSTEMS = ("model-a", "model-b", "model-c")


def _add_io_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--ref-format", default="auto", choices=("auto", *FORMATS), help="reference file format")
    p.add_argument("--hyp-format", default="auto", choices=("auto", *FORMATS), help="hypothesis file format")
    p.add_argument("--encoding", default="utf-8", help="text encoding of input files (e.g. cp949)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="korean-asr-eval",
        description="Pin Korean ASR scoring rules (normalization profiles) and see how they move CER and rankings.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("profiles", help="list built-in profiles (and any given .toml files)")
    p.add_argument("files", nargs="*", help="optional profile .toml files to describe as well")

    p = sub.add_parser("normalize", help="normalize text with a profile")
    p.add_argument("--profile", default="basic@1", help="profile id or .toml path (default basic@1)")
    p.add_argument("--trace", action="store_true", help="show the text after every step")
    p.add_argument("text", nargs="*", help="text to normalize (default: read lines from stdin)")

    p = sub.add_parser("score", help="score one hypothesis file against a reference file")
    p.add_argument("--ref", required=True, help="reference file (tsv, jsonl, trn or txt)")
    p.add_argument("--hyp", required=True, help="hypothesis file")
    p.add_argument("--profile", default="basic@1", help="profile id or .toml path (default basic@1)")
    p.add_argument("--format", default="text", choices=("text", "markdown", "json"))
    p.add_argument("--json", action="store_true", help="shortcut for --format json")
    _add_io_args(p)

    p = sub.add_parser("compare", help="compare several systems under several profiles")
    p.add_argument("--ref", required=True, help="reference file")
    p.add_argument("--hyp", action="append", required=True, metavar="NAME=FILE",
                   help="a system's hypothesis file; repeat for each system")
    p.add_argument("--profile", action="append", default=None,
                   help="profile id or .toml path; repeat (first = baseline). "
                        f"Default: {', '.join(DEFAULT_PROFILES)}")
    p.add_argument("--top", type=int, default=5, help="most-changed utterances per system (default 5)")
    p.add_argument("--format", default="text", choices=("text", "markdown", "json"))
    _add_io_args(p)

    p = sub.add_parser("demo", help="run the bundled practice sample (no files, no network)")
    p.add_argument("--format", default="text", choices=("text", "markdown", "json"))
    return parser


def _render_comparison(c: Comparison, fmt: str) -> str:
    if fmt == "json":
        return to_json(c.to_dict())
    return comparison_markdown(c) if fmt == "markdown" else comparison_text(c)


def _cmd_profiles(args: argparse.Namespace) -> str:
    out = []
    for prof in list_profiles():
        out.append(prof.describe())
        out.append(f"    {prof.description}")
    for f in args.files:
        prof = load_profile(f)
        out.append(prof.describe())
        if prof.description:
            out.append(f"    {prof.description}")
    return "\n".join(out) + "\n"


def _cmd_normalize(args: argparse.Namespace) -> str:
    prof = resolve_profile(args.profile)
    texts = args.text if args.text else [ln.rstrip("\n") for ln in sys.stdin]
    out = []
    for text in texts:
        if args.trace:
            out.append(f"profile: {prof.id} (fp {prof.fingerprint})")
            out.append(f"input: {text}")
            for t in normalize_trace(text, prof):
                note = "  (unchanged)" if t.before == t.after else ""
                out.append(f"  {t.step}: {t.after}{note}")
            out.append(f"result: {normalize(text, prof)}")
        else:
            out.append(normalize(text, prof))
    return "\n".join(out) + "\n"


def _cmd_score(args: argparse.Namespace) -> str:
    refs = read_pairs(args.ref, args.ref_format, args.encoding)
    hyps = read_pairs(args.hyp, args.hyp_format, args.encoding)
    result = score(refs, hyps, args.profile)
    fmt = "json" if args.json else args.format
    if fmt == "json":
        return to_json(result.to_dict())
    return score_markdown(result) if fmt == "markdown" else score_text(result)


def _split_hyp(spec: str) -> tuple[str, str]:
    name, sep, path = spec.partition("=")
    if not sep:
        return Path(spec).stem, spec
    if not name or not path:
        raise InputFormatError(f"--hyp expects NAME=FILE, got {spec!r}")
    return name, path


def _cmd_compare(args: argparse.Namespace) -> str:
    refs = read_pairs(args.ref, args.ref_format, args.encoding)
    systems = {}
    for spec in args.hyp:
        name, path = _split_hyp(spec)
        if name in systems:
            raise InputFormatError(f"system name {name!r} given twice; use NAME=FILE with distinct names")
        systems[name] = read_pairs(path, args.hyp_format, args.encoding)
    profiles = args.profile or list(DEFAULT_PROFILES)
    return _render_comparison(compare(refs, systems, profiles, top_n=args.top), args.format)


def _cmd_demo(args: argparse.Namespace) -> str:
    sample = resources.files("korean_asr_eval").joinpath("data", "sample")
    refs = read_pairs(str(sample.joinpath("ref.trn")))
    systems = {
        name: read_pairs(str(sample.joinpath(f"hyp_{name}.tsv"))) for name in DEMO_SYSTEMS
    }
    comparison = compare(refs, systems, DEFAULT_PROFILES, top_n=2)
    body = _render_comparison(comparison, args.format)
    if args.format == "json":
        return body
    tail = (
        "\nSame systems, same audio, different scoring rule: the winner changes. "
        "Pin the rule (profile id + fingerprint) whenever you publish a number.\n"
        "Try: korean-asr-eval normalize --trace --profile kspon-phonetic@1 "
        "\"o/ (70%)/(칠십 퍼센트) 정도는 b/ 음/ 됐어요+ n/\"\n"
    )
    return DEMO_BANNER + "\n\n" + body + tail


_COMMANDS = {
    "profiles": _cmd_profiles,
    "normalize": _cmd_normalize,
    "score": _cmd_score,
    "compare": _cmd_compare,
    "demo": _cmd_demo,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    for stream in (sys.stdout, sys.stderr):
        try:  # make output independent of the locale (LC_ALL=C etc.)
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", EmptyReferenceWarning)
            text = _COMMANDS[args.command](args)
    except KoreanAsrEvalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot read {exc.filename or 'input'}: {exc.strerror}", file=sys.stderr)
        return 2
    seen: set[str] = set()
    for w in caught:
        msg = str(w.message)
        if msg not in seen:
            seen.add(msg)
            print(f"warning: {msg}", file=sys.stderr)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
