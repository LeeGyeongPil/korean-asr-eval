"""Reading reference/hypothesis files and lining them up by utterance id.

Supported formats (chosen by file suffix, or pass ``fmt=``):

* ``tsv``   - ``id<TAB>text`` per line
* ``jsonl`` - ``{"id": ..., "text": ...}`` per line
* ``trn``   - ``path :: transcript`` (KsponSpeech style); the id is the file stem of ``path``
* ``txt``   - one transcript per line; ids are line numbers starting at 1
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from .errors import IdMismatchError, InputFormatError

FORMATS = ("tsv", "jsonl", "trn", "txt")


def read_pairs(
    path: str | Path, fmt: str = "auto", encoding: str = "utf-8"
) -> dict[str, str]:
    """Read ``{id: text}`` from a file.

    Args:
        path: file to read.
        fmt: ``"auto"`` (by suffix) or one of :data:`FORMATS`.
        encoding: text encoding, e.g. ``"cp949"`` for original KsponSpeech files.

    Raises:
        InputFormatError: unknown format, malformed line, duplicate id or bad encoding.
    """
    p = Path(path)
    if fmt == "auto":
        fmt = p.suffix.lower().lstrip(".")
        if fmt not in FORMATS:
            raise InputFormatError(
                f"cannot guess the format of {p.name}; pass fmt= one of {', '.join(FORMATS)}"
            )
    elif fmt not in FORMATS:
        raise InputFormatError(f"unknown format {fmt!r}; choose one of {', '.join(FORMATS)}")
    try:
        raw = p.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise InputFormatError(
            f"{p.name} is not valid {encoding}; pass encoding= (for example cp949)"
        ) from exc
    if raw.startswith("﻿"):
        raw = raw[1:]
    return parse_pairs(raw, fmt, source=p.name)


def parse_pairs(raw: str, fmt: str, source: str = "<text>") -> dict[str, str]:
    """Parse already-decoded text. See :func:`read_pairs`."""
    out: dict[str, str] = {}

    def put(key: str, value: str, lineno: int) -> None:
        if key in out:
            raise InputFormatError(f"{source}:{lineno}: duplicate id {key!r}")
        out[key] = value

    for lineno, line in enumerate(raw.splitlines(), start=1):
        if fmt == "txt":
            put(str(lineno), line.strip(), lineno)
            continue
        if not line.strip():
            continue
        if fmt == "tsv":
            key, sep, text = line.partition("\t")
            if not sep or not key.strip():
                raise InputFormatError(
                    f"{source}:{lineno}: expected 'id<TAB>text'; "
                    "for an empty transcript write the id followed by a tab"
                )
            put(key.strip(), text.strip(), lineno)
        elif fmt == "jsonl":
            try:
                obj = json.loads(line)
                key, text = obj["id"], obj["text"]
            except (ValueError, KeyError, TypeError) as exc:
                raise InputFormatError(
                    f'{source}:{lineno}: expected a JSON object like {{"id": "u1", "text": "..."}}'
                ) from exc
            if not isinstance(text, str):
                raise InputFormatError(f"{source}:{lineno}: 'text' must be a string")
            put(str(key), text.strip(), lineno)
        else:  # trn
            path_part, sep, text = line.partition(" :: ")
            if not sep:
                raise InputFormatError(
                    f"{source}:{lineno}: expected 'path :: transcript' (note the spaces around '::')"
                )
            stem = PurePosixPath(path_part.strip().replace("\\", "/")).stem
            if not stem:
                raise InputFormatError(f"{source}:{lineno}: empty audio path before ' :: '")
            put(stem, text.strip(), lineno)
    return out


def align(
    refs: Mapping[str, str], hyps: Mapping[str, str], system: str | None = None
) -> tuple[list[str], list[str], list[str]]:
    """Line up two ``{id: text}`` mappings; returns ``(ids, ref_texts, hyp_texts)``.

    The order follows ``refs``.

    Raises:
        IdMismatchError: some reference id has no hypothesis, or the reverse.
    """
    missing = [i for i in refs if i not in hyps]
    extra = [i for i in hyps if i not in refs]
    if missing or extra:
        raise IdMismatchError(missing, extra, system)
    ids = list(refs)
    return ids, [refs[i] for i in ids], [hyps[i] for i in ids]
