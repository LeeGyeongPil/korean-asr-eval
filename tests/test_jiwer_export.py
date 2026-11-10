"""AC-5: the exported jiwer transform reproduces score()."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import jiwer
import pytest

from korean_asr_eval import list_profiles, read_pairs, score, to_jiwer_transform

SYSTEMS = ("model-a", "model-b", "model-c")


def _sample() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    d = resources.files("korean_asr_eval").joinpath("data", "sample")
    refs = read_pairs(str(d.joinpath("ref.trn")))
    return refs, {n: read_pairs(str(d.joinpath(f"hyp_{n}.tsv"))) for n in SYSTEMS}


@pytest.mark.parametrize("profile", list_profiles(), ids=lambda p: p.id)
def test_transform_matches_score(profile) -> None:  # type: ignore[no-untyped-def]
    refs, systems = _sample()
    ref_list = list(refs.values())
    for hyps in systems.values():
        hyp_list = [hyps[i] for i in refs]
        s = score(refs, hyps, profile)

        t = to_jiwer_transform(profile)
        cer = jiwer.cer(ref_list, hyp_list, reference_transform=t, hypothesis_transform=t)
        assert abs(cer - s.cer) < 1e-9

        t_ns = to_jiwer_transform(profile, ignore_space=True)
        cer_ns = jiwer.cer(ref_list, hyp_list, reference_transform=t_ns, hypothesis_transform=t_ns)
        assert abs(cer_ns - s.cer_nospace) < 1e-9

        t_w = to_jiwer_transform(profile, unit="word")
        wer = jiwer.wer(ref_list, hyp_list, reference_transform=t_w, hypothesis_transform=t_w)
        assert abs(wer - s.wer) < 1e-9


def test_transform_on_fixture_files(fixtures_dir: Path) -> None:
    refs = read_pairs(fixtures_dir / "ref.trn")
    hyps = read_pairs(fixtures_dir / "hyp_a.tsv")
    t = to_jiwer_transform("kspon-phonetic@1")
    value = jiwer.cer(list(refs.values()), [hyps[i] for i in refs],
                      reference_transform=t, hypothesis_transform=t)
    assert abs(value - score(refs, hyps, "kspon-phonetic@1").cer) < 1e-9


def test_bad_unit_is_rejected() -> None:
    from korean_asr_eval import KoreanAsrEvalError

    with pytest.raises(KoreanAsrEvalError, match="unit must be"):
        to_jiwer_transform("basic@1", unit="phoneme")
    with pytest.raises(KoreanAsrEvalError, match="ignore_space"):
        to_jiwer_transform("basic@1", unit="word", ignore_space=True)
