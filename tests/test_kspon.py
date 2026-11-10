"""AC-2: KsponSpeech transcript conventions."""

from __future__ import annotations

from korean_asr_eval import normalize

RAW = "o/ (70%)/(칠십 퍼센트) 정도는 b/ 음/ 됐어요+ n/"


def test_dual_choice_and_tags() -> None:
    assert normalize(RAW, "kspon-phonetic@1") == "칠십 퍼센트 정도는 음 됐어요"
    assert normalize(RAW, "kspon-spelling@1") == "70퍼센트 정도는 음 됐어요"
    assert normalize("b/ n/", "kspon-phonetic@1") == ""
    assert normalize("b/ n/", "kspon-spelling@1") == ""


def test_all_noise_tags_removed() -> None:
    assert normalize("b/ n/ o/ l/ u/ 안녕", "kspon-phonetic@1") == "안녕"


def test_tag_letters_inside_words_are_kept() -> None:
    # 'b/' only counts as a tag when it stands alone as a token.
    assert normalize("tab/ 안녕", "kspon-phonetic@1") == "tab 안녕"


def test_disfluency_and_repetition_marks() -> None:
    assert normalize("그/ 그 자료를 못 봤어요+", "kspon-spelling@1") == "그 그 자료를 못 봤어요"
    assert normalize("뭐*라고", "kspon-spelling@1") == "뭐라고"


def test_percent_word_is_a_parameter() -> None:
    from korean_asr_eval import Step

    assert Step.make("percent_word", word="프로").apply("5%") == "5프로"
