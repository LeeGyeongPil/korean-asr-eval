"""Unit tests for individual normalization steps and their parameter checks."""

from __future__ import annotations

import unicodedata

import pytest

from korean_asr_eval import ProfileFormatError, Step, normalize_trace


def test_nfc_composes_hangul() -> None:
    nfd = unicodedata.normalize("NFD", "됐어요")
    assert len(nfd) > 3
    assert Step.make("nfc").apply(nfd) == "됐어요"


def test_punct_to_space_and_keep() -> None:
    assert Step.make("punct_to_space").apply("a.b,c") == "a b c"
    assert Step.make("punct_to_space", keep=".").apply("a.b,c") == "a.b c"
    assert Step.make("punct_to_space").apply("3.5%") == "3 5 "  # '%' is a symbol too


def test_collapse_spaces_strips_and_joins() -> None:
    assert Step.make("collapse_spaces").apply("  a \t b\n") == "a b"


def test_replace_is_ordered_and_literal() -> None:
    step = Step.make("replace", pairs={"a": "b", "b": "c"})
    assert step.apply("a") == "c"  # later pairs see earlier output


def test_defaults_are_recorded_in_params() -> None:
    assert Step.make("kspon_dual").params == {"choose": "spelling"}


def test_bad_step_name_lists_available() -> None:
    with pytest.raises(ProfileFormatError, match="available steps"):
        Step.make("nope")


def test_bad_parameter_name_and_value() -> None:
    with pytest.raises(ProfileFormatError, match="no parameter"):
        Step.make("nfc", form="NFKC")
    with pytest.raises(ProfileFormatError, match="spelling"):
        Step.make("kspon_dual", choose="third")
    with pytest.raises(ProfileFormatError, match="empty 'old'"):
        Step.make("replace", pairs={"": "x"})


def test_trace_reports_each_step() -> None:
    trace = normalize_trace("A!", "basic@1")
    assert [t.step for t in trace] == ["nfc", "lowercase", "punct_to_space", "collapse_spaces"]
    assert trace[0].before == "A!"
    assert trace[-1].after == "a"
