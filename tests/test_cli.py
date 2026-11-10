"""AC-1 and CLI behaviour."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from korean_asr_eval.cli import main


def test_demo_exit_zero_and_shows_rank_flip(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert "연습용 합성 샘플" in lines[0]
    for pid in ("none@1", "kspon-spelling@1", "kspon-phonetic@1"):
        assert pid in out
    assert "kspon-spelling@1: model-b <" in out  # model-b ranks first under spelling
    assert "kspon-phonetic@1: model-a <" in out  # model-a ranks first under pronunciation
    assert sum(1 for ln in lines if ln.startswith("rank flip")) >= 1


def test_demo_runs_as_module_in_other_cwd_and_c_locale(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    env.update({"LC_ALL": "C", "TZ": "Pacific/Auckland"})
    proc = subprocess.run(
        [sys.executable, "-m", "korean_asr_eval", "demo"],
        cwd=tmp_path, env=env, capture_output=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert "연습용 합성 샘플" in proc.stdout.decode("utf-8")


def test_profiles_lists_builtin_and_toml(
    fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["profiles", str(fixtures_dir / "my-lab.toml")]) == 0
    out = capsys.readouterr().out
    assert "kspon-phonetic@1  fp " in out and "my-lab@2" in out


def test_normalize_trace(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["normalize", "--trace", "--profile", "kspon-phonetic@1", "b/ 안녕+"]) == 0
    out = capsys.readouterr().out
    assert "kspon_noise_tags" in out and "result: 안녕" in out


def test_normalize_reads_stdin(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("A!\nB?\n"))
    assert main(["normalize", "--profile", "basic@1"]) == 0
    assert capsys.readouterr().out == "a\nb\n"


def test_score_text_and_markdown(fixtures_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["score", "--ref", str(fixtures_dir / "ref.trn"), "--hyp", str(fixtures_dir / "hyp_b.tsv"),
            "--profile", "kspon-phonetic@1"]
    assert main(base) == 0
    assert "CER-nospace" in capsys.readouterr().out
    assert main([*base, "--format", "markdown"]) == 0
    assert "| CER |" in capsys.readouterr().out


def test_bad_inputs_exit_2(tmp_path: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ref = str(fixtures_dir / "ref.trn")
    assert main(["score", "--ref", ref, "--hyp", str(tmp_path / "nope.tsv")]) == 2
    assert "error:" in capsys.readouterr().err
    assert main(["compare", "--ref", ref, "--hyp", "=x.tsv"]) == 2
    assert "NAME=FILE" in capsys.readouterr().err
    hyp = str(fixtures_dir / "hyp_a.tsv")
    assert main(["compare", "--ref", ref, "--hyp", f"a={hyp}", "--hyp", f"a={hyp}"]) == 2
    assert "twice" in capsys.readouterr().err


def test_empty_reference_warning_is_printed_not_fatal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ref = tmp_path / "r.tsv"
    hyp = tmp_path / "h.tsv"
    ref.write_text("a\tb/ n/\nb\t안녕\n", encoding="utf-8")
    hyp.write_text("a\t네\nb\t안녕\n", encoding="utf-8")
    assert main(["score", "--ref", str(ref), "--hyp", str(hyp), "--profile", "kspon-phonetic@1"]) == 0
    assert "warning:" in capsys.readouterr().err


def test_quickstart_example_runs(capsys: pytest.CaptureFixture[str]) -> None:
    import runpy

    path = Path(__file__).resolve().parent.parent / "examples" / "quickstart.py"
    runpy.run_path(str(path), run_name="__main__")
    assert "rank flip" in capsys.readouterr().out


def test_argparse_errors_exit_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["score"])
    assert exc.value.code == 2


# --- split encodings: cp949 reference (original KsponSpeech) + UTF-8 hypotheses ---


def _cp949_ref_and_utf8_hyps(tmp_path: Path) -> tuple[Path, Path, Path]:
    ref = tmp_path / "ref.tsv"
    ref.write_bytes("a\t안녕\nb\t반가워\n".encode("cp949"))
    hyp1 = tmp_path / "h1.tsv"
    hyp1.write_text("a\t안녕\nb\t반가워\n", encoding="utf-8")
    hyp2 = tmp_path / "h2.tsv"
    hyp2.write_text("a\t안녕\nb\t반가요\n", encoding="utf-8")
    return ref, hyp1, hyp2


def test_score_ref_encoding_cp949_with_utf8_hyp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ref, hyp1, _ = _cp949_ref_and_utf8_hyps(tmp_path)
    code = main(["score", "--ref", str(ref), "--hyp", str(hyp1), "--ref-encoding", "cp949", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert "0.0" in out  # identical text -> CER 0


def test_compare_hyp_encoding_applies_to_all_hyps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ref, hyp1, hyp2 = _cp949_ref_and_utf8_hyps(tmp_path)
    code = main([
        "compare", "--ref", str(ref), "--ref-encoding", "cp949",
        "--hyp", f"x={hyp1}", "--hyp", f"y={hyp2}", "--hyp-encoding", "utf-8",
    ])
    assert code == 0
    assert "x" in capsys.readouterr().out


def test_encoding_shortcut_still_applies_to_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ref = tmp_path / "r.tsv"
    ref.write_bytes("a\t안녕\n".encode("cp949"))
    hyp = tmp_path / "h.tsv"
    hyp.write_bytes("a\t안녕\n".encode("cp949"))
    assert main(["score", "--ref", str(ref), "--hyp", str(hyp), "--encoding", "cp949"]) == 0


def test_cli_decode_error_names_real_options(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ref, hyp1, _ = _cp949_ref_and_utf8_hyps(tmp_path)
    assert main(["score", "--ref", str(ref), "--hyp", str(hyp1)]) == 2
    err = capsys.readouterr().err
    assert "--ref-encoding" in err and "--encoding" in err
    assert "pass encoding=" not in err
    # hypothesis side: UTF-8 ref, cp949 hyp
    ref2 = tmp_path / "r2.tsv"
    ref2.write_text("a\t안녕\n", encoding="utf-8")
    hyp2 = tmp_path / "h3.tsv"
    hyp2.write_bytes("a\t안녕\n".encode("cp949"))
    assert main(["score", "--ref", str(ref2), "--hyp", str(hyp2)]) == 2
    err = capsys.readouterr().err
    assert "--hyp-encoding" in err and "pass encoding=" not in err
