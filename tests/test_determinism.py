"""AC-7: JSON output records provenance and is byte-stable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from korean_asr_eval.cli import main


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    assert main(argv) == 0
    return capsys.readouterr().out


def test_json_bytes_stable(
    fixtures_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "score", "--ref", str(fixtures_dir / "ref.trn"), "--hyp", str(fixtures_dir / "hyp_a.tsv"),
        "--profile", str(fixtures_dir / "my-lab.toml"), "--json",
    ]
    first = _run(argv, capsys)
    second = _run(argv, capsys)
    assert first.encode("utf-8") == second.encode("utf-8")

    data = json.loads(first)
    assert data["profile_id"] == "my-lab@2"
    for key in ("fingerprint", "korean_asr_eval_version", "jiwer_version"):
        assert data[key]
    # no timestamps and no absolute paths anywhere in the output
    lowered = first.lower()
    for forbidden in ("timestamp", "created", "date", str(fixtures_dir), str(tmp_path)):
        assert forbidden.lower() not in lowered


def test_compare_json_bytes_stable(fixtures_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "compare", "--ref", str(fixtures_dir / "ref.trn"),
        "--hyp", f"a={fixtures_dir / 'hyp_a.tsv'}", "--hyp", f"b={fixtures_dir / 'hyp_b.tsv'}",
        "--format", "json",
    ]
    assert _run(argv, capsys) == _run(argv, capsys)


def test_demo_json_stable(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(["demo", "--format", "json"], capsys) == _run(["demo", "--format", "json"], capsys)
