"""AC-3 / AC-4 / AC-9: scoring semantics."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from korean_asr_eval import (
    EmptyReferenceWarning,
    IdMismatchError,
    InputFormatError,
    read_pairs,
    score,
)

KSPON_REF = "o/ (70%)/(칠십 퍼센트) 정도는 b/ 음/ 됐어요+ n/"
NO_NONE = ["basic@1", "kspon-spelling@1", "kspon-phonetic@1"]


def _sentences(fixtures_dir: Path) -> list[str]:
    return list(read_pairs(fixtures_dir / "sentences.txt").values())


def test_symmetric_and_nfc(fixtures_dir: Path) -> None:
    sentences = _sentences(fixtures_dir)
    nfd = [unicodedata.normalize("NFD", s) for s in sentences]
    for profile in NO_NONE:
        nfc_result = score(sentences, sentences, profile).to_dict()
        nfd_result = score(sentences, nfd, profile).to_dict()
        assert nfd_result == nfc_result, profile
        for x in sentences:
            assert score([x], [x], profile).cer == 0.0


def test_none_profile_is_sensitive_to_nfd() -> None:
    # 'none@1' is the "no normalization" baseline: NFD inflates CER, which is the point.
    nfd = unicodedata.normalize("NFD", "됐어요")
    assert score(["됐어요"], [nfd], "none@1").cer > 1.0


def test_probe_numbers() -> None:
    raw = score([KSPON_REF], ["칠십 퍼센트 정도는 음 됐어요."], "none@1")
    assert round(raw.cer, 4) == 0.5429
    normalized = score([KSPON_REF], ["칠십 퍼센트 정도는 음 됐어요."], "kspon-phonetic@1")
    assert normalized.cer == 0.0

    c = score([KSPON_REF], ["칠십퍼센트정도는 음 됬어요"], "kspon-phonetic@1")
    assert round(c.cer, 4) == 0.1875
    assert round(c.cer_nospace, 4) == 0.0833
    assert round(c.wer, 4) == 0.8
    assert (c.substitutions, c.deletions, c.insertions) == (1, 2, 0)

    # Same hypothesis against the spelling side: '70퍼센트' vs '칠십 퍼센트' is now wrong.
    # (The probe kept '%' and got 0.4615; kspon-spelling@1 spells it out, so 3/15 here.)
    s = score([KSPON_REF], ["칠십 퍼센트 정도는 음 됐어요"], "kspon-spelling@1")
    assert round(s.cer, 4) == 0.2
    assert (s.substitutions, s.deletions, s.insertions) == (2, 0, 1)


def test_micro_vs_macro() -> None:
    s = score(["가나다라", "가"], ["가나다라", "나"], "basic@1")
    assert s.cer == pytest.approx(1 / 5)  # 1 error over 5 reference chars
    assert s.cer_macro == pytest.approx(0.5)  # mean of 0.0 and 1.0
    assert s.n_utts == 2 and s.ref_chars == 5


def test_empty_reference_policy() -> None:
    with pytest.warns(EmptyReferenceWarning, match="1 reference"):
        s = score(["b/ n/", "안녕하세요"], ["네", "안녕하세요"], "kspon-phonetic@1")
    assert s.empty_refs == 1
    assert s.insertions == 1  # the hypothesis char of the empty reference
    assert s.cer == pytest.approx(1 / 5)  # micro includes it
    assert s.cer_macro == 0.0  # macro excludes it
    assert s.utterances[0].cer is None


def test_all_references_empty_gives_none() -> None:
    with pytest.warns(EmptyReferenceWarning):
        s = score(["n/"], ["가"], "kspon-phonetic@1")
    assert s.cer is None and s.cer_macro is None and s.wer is None


def test_dict_inputs_match_by_id() -> None:
    s = score({"a": "가나", "b": "다"}, {"b": "다", "a": "가나"}, "basic@1")
    assert s.cer == 0.0
    assert [u.id for u in s.utterances] == ["a", "b"]


def test_id_mismatch_raises_with_ids() -> None:
    with pytest.raises(IdMismatchError) as err:
        score({"a": "x", "b": "y"}, {"a": "x", "c": "y"}, "basic@1", system="sys1")
    assert err.value.missing == ["b"] and err.value.extra == ["c"]
    assert "sys1" in str(err.value)


def test_list_length_and_type_errors() -> None:
    with pytest.raises(InputFormatError, match="one-to-one"):
        score(["a", "b"], ["a"], "basic@1")
    with pytest.raises(InputFormatError, match="not a single str"):
        score("abc", "abc", "basic@1")  # type: ignore[arg-type]
    with pytest.raises(InputFormatError, match="both be dicts"):
        score({"a": "x"}, ["x"], "basic@1")
