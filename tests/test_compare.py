"""AC-8: compare() and `korean-asr-eval compare`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from korean_asr_eval import InputFormatError, compare, read_pairs
from korean_asr_eval.cli import main


def _systems(fixtures_dir: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    refs = read_pairs(fixtures_dir / "ref.trn")
    return refs, {
        "a": read_pairs(fixtures_dir / "hyp_a.tsv"),
        "b": read_pairs(fixtures_dir / "hyp_b.tsv"),
    }


def test_ranks_deltas_flips(fixtures_dir: Path) -> None:
    refs, systems = _systems(fixtures_dir)
    c = compare(refs, systems, ["none@1", "kspon-phonetic@1"])
    assert c.ranks["none@1"] == ["a", "b"]
    assert c.ranks["kspon-phonetic@1"] == ["b", "a"]
    assert [f.pair for f in c.rank_flips] == [("a", "b")]
    flip = c.rank_flips[0]
    assert (flip.ahead_in_a, flip.ahead_in_b) == ("a", "b")
    # deltas are measured against the first profile, in percentage points
    assert c.deltas_pp["a"]["none@1"] == 0.0
    expected = (c.table["a"]["kspon-phonetic@1"].cer - c.table["a"]["none@1"].cer) * 100
    assert c.deltas_pp["a"]["kspon-phonetic@1"] == pytest.approx(expected)
    # the utterance with the tag text changes most for system a
    assert c.top_changed["a"][0].id in {"f1", "f2", "f3"}
    assert all(ch.delta_pp < 0 for ch in c.top_changed["a"])


def test_no_flip_when_profiles_agree(fixtures_dir: Path) -> None:
    refs, systems = _systems(fixtures_dir)
    c = compare(refs, systems, ["kspon-phonetic@1"])
    assert c.rank_flips == []
    assert c.top_changed == {"a": [], "b": []}


def test_compare_cli_json(fixtures_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([
        "compare",
        "--ref", str(fixtures_dir / "ref.trn"),
        "--hyp", f"a={fixtures_dir / 'hyp_a.tsv'}",
        "--hyp", f"b={fixtures_dir / 'hyp_b.tsv'}",
        "--profile", "none@1", "--profile", "kspon-phonetic@1",
        "--format", "json",
    ])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    for key in ("table", "ranks", "deltas_pp", "rank_flips", "top_changed"):
        assert key in data
    assert data["rank_flips"][0]["pair"] == ["a", "b"]


def test_compare_markdown_and_text(fixtures_dir: Path) -> None:
    refs, systems = _systems(fixtures_dir)
    c = compare(refs, systems, ["none@1", "kspon-phonetic@1"])
    assert "| system |" in c.to_markdown() and "Rank flips" in c.to_markdown()
    assert "rank flip" in c.to_text()


def test_compare_input_errors(fixtures_dir: Path) -> None:
    refs, systems = _systems(fixtures_dir)
    with pytest.raises(InputFormatError, match="at least one system"):
        compare(refs, {})
    with pytest.raises(InputFormatError, match="duplicate profile"):
        compare(refs, systems, ["basic@1", "basic@1"])
    with pytest.raises(InputFormatError, match="at least one profile"):
        compare(refs, systems, [])
