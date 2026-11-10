"""AC-9 (ids) and input readers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from korean_asr_eval import IdMismatchError, InputFormatError, read_pairs
from korean_asr_eval.cli import main
from korean_asr_eval.io import align


def test_id_mismatch_error() -> None:
    with pytest.raises(IdMismatchError) as err:
        align({"a": "1", "b": "2", "c": "3"}, {"a": "1", "c": "3", "d": "4"}, "sys")
    assert err.value.missing == ["b"]
    assert err.value.extra == ["d"]
    assert "b" in str(err.value) and "d" in str(err.value)


def test_id_mismatch_cli_exit_2(
    tmp_path: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hyp = tmp_path / "hyp.tsv"
    hyp.write_text("f1\t가\nf2\t나\n", encoding="utf-8")  # f3 missing
    code = main(["score", "--ref", str(fixtures_dir / "ref.trn"), "--hyp", str(hyp)])
    err = capsys.readouterr().err
    assert code == 2
    assert "f3" in err and "missing" in err


def test_trn_ids_are_file_stems(fixtures_dir: Path) -> None:
    refs = read_pairs(fixtures_dir / "ref.trn")
    assert list(refs) == ["f1", "f2", "f3"]
    assert refs["f2"] == "오늘 b/ 날씨가 좋아요"


def test_tsv_jsonl_txt(tmp_path: Path) -> None:
    (tmp_path / "a.tsv").write_text("x\t가 나\n\ny\t\n", encoding="utf-8")
    assert read_pairs(tmp_path / "a.tsv") == {"x": "가 나", "y": ""}
    (tmp_path / "a.jsonl").write_text(
        json.dumps({"id": "x", "text": "가"}, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    assert read_pairs(tmp_path / "a.jsonl") == {"x": "가"}
    (tmp_path / "a.txt").write_text("가\n\n나\n", encoding="utf-8")
    assert read_pairs(tmp_path / "a.txt") == {"1": "가", "2": "", "3": "나"}


def test_cp949_and_bom(tmp_path: Path) -> None:
    p = tmp_path / "k.tsv"
    p.write_bytes("a\t안녕\n".encode("cp949"))
    assert read_pairs(p, encoding="cp949") == {"a": "안녕"}
    with pytest.raises(InputFormatError, match="encoding"):
        read_pairs(p)  # utf-8 cannot decode it
    q = tmp_path / "bom.tsv"
    q.write_bytes("﻿a\t안녕\n".encode("utf-8"))
    assert read_pairs(q) == {"a": "안녕"}


def test_malformed_lines_have_line_numbers(tmp_path: Path) -> None:
    bad_tsv = tmp_path / "b.tsv"
    bad_tsv.write_text("a\t1\nno tab here\n", encoding="utf-8")
    with pytest.raises(InputFormatError, match=r"b\.tsv:2"):
        read_pairs(bad_tsv)
    bad_trn = tmp_path / "b.trn"
    bad_trn.write_text("x.wav :: ok\nx2.wav:nospace\n", encoding="utf-8")
    with pytest.raises(InputFormatError, match=r"b\.trn:2"):
        read_pairs(bad_trn)
    dup = tmp_path / "d.tsv"
    dup.write_text("a\t1\na\t2\n", encoding="utf-8")
    with pytest.raises(InputFormatError, match="duplicate id"):
        read_pairs(dup)


def test_unknown_suffix_and_format(tmp_path: Path) -> None:
    p = tmp_path / "x.dat"
    p.write_text("a\t1\n", encoding="utf-8")
    with pytest.raises(InputFormatError, match="cannot guess"):
        read_pairs(p)
    assert read_pairs(p, fmt="tsv") == {"a": "1"}
    with pytest.raises(InputFormatError, match="unknown format"):
        read_pairs(p, fmt="csv")
