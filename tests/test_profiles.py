"""AC-6 / AC-7: pinned built-in profiles, TOML profiles, rejection of unknown ones."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from korean_asr_eval import (
    Profile,
    ProfileFormatError,
    Step,
    UnknownProfileError,
    get_profile,
    list_profiles,
    load_profile,
    normalize,
)
from korean_asr_eval.cli import main


def test_builtin_fingerprints_pinned(golden_dir: Path) -> None:
    golden = json.loads((golden_dir / "profiles.json").read_text(encoding="utf-8"))
    current = {p.id: p.fingerprint for p in list_profiles()}
    assert current == golden, (
        "A built-in profile changed. Do not edit it: add a new version (e.g. name@2) instead."
    )
    assert list(current) == ["none@1", "basic@1", "kspon-spelling@1", "kspon-phonetic@1"]


def test_unknown_profile_rejected_with_available_ids() -> None:
    with pytest.raises(UnknownProfileError) as err:
        get_profile("kspon-spelling@9")
    assert "unknown profile: kspon-spelling@9" in str(err.value)
    assert "kspon-phonetic@1" in str(err.value)


def test_unknown_profile_cli_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["normalize", "--profile", "kspon-spelling@9", "가"])
    err = capsys.readouterr().err
    assert code == 2
    assert "unknown profile: kspon-spelling@9" in err
    for pid in ("none@1", "basic@1", "kspon-spelling@1", "kspon-phonetic@1"):
        assert pid in err


def test_fingerprint_changes_when_a_step_changes() -> None:
    a = Profile("x", 1, (Step.make("percent_word", word="퍼센트"),))
    b = Profile("x", 1, (Step.make("percent_word", word="프로"),))
    assert a.fingerprint != b.fingerprint
    assert len(a.fingerprint) == 12


def test_user_toml_extends(fixtures_dir: Path) -> None:
    prof = load_profile(fixtures_dir / "my-lab.toml")
    assert prof.id == "my-lab@2"
    assert prof.fingerprint != get_profile("basic@1").fingerprint
    assert normalize("三十 ㎏!", prof) == "삼십 킬로그램"
    # also reachable by path string
    assert normalize("三十", str(fixtures_dir / "my-lab.toml")) == "삼십"


def test_replace_keys_match_nfc_text(fixtures_dir: Path) -> None:
    import unicodedata

    prof = load_profile(fixtures_dir / "my-lab.toml")
    assert normalize(unicodedata.normalize("NFD", "三十"), prof) == "삼십"


def test_toml_errors_say_how_to_fix(tmp_path: Path) -> None:
    def write(text: str) -> Path:
        p = tmp_path / "p.toml"
        p.write_text(text, encoding="utf-8")
        return p

    with pytest.raises(ProfileFormatError, match="missing required key 'version'"):
        load_profile(write('name = "x"\n'))
    with pytest.raises(ProfileFormatError, match="unknown key"):
        load_profile(write('name = "x"\nversion = 1\nextend = "basic@1"\n'))
    with pytest.raises(ProfileFormatError, match="not valid TOML"):
        load_profile(write("name = \n"))
    with pytest.raises(UnknownProfileError):
        load_profile(write('name = "x"\nversion = 1\nextends = "basic@7"\n'))
    with pytest.raises(ProfileFormatError, match="invalid profile version"):
        load_profile(write('name = "x"\nversion = 0\n'))
    with pytest.raises(ProfileFormatError, match="invalid profile name"):
        load_profile(write('name = "Bad Name"\nversion = 1\n'))
    with pytest.raises(ProfileFormatError, match="cannot read"):
        load_profile(tmp_path / "missing.toml")


def test_toml_extra_steps_are_appended(tmp_path: Path) -> None:
    p = tmp_path / "p.toml"
    p.write_text(
        'name = "pct"\nversion = 1\nextends = "basic@1"\n'
        '[[steps]]\nname = "percent_word"\nword = "프로"\n',
        encoding="utf-8",
    )
    prof = load_profile(p)
    assert prof.steps[-1].name == "percent_word"
    assert prof.steps[-1].params == {"word": "프로"}
