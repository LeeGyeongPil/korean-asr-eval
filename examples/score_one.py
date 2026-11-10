"""Score one hypothesis under two rules.

Run with:  uv run python examples/score_one.py
"""

from korean_asr_eval import normalize, score

ref = "o/ (70%)/(칠십 퍼센트) 정도는 b/ 음/ 됐어요+ n/"
hyp = "칠십 퍼센트 정도는 음 됐어요."

print(normalize(ref, "kspon-phonetic@1"))

r = score([ref], [hyp], "kspon-phonetic@1")
print(r.profile_id, r.fingerprint, "CER", r.cer, "CER-nospace", r.cer_nospace, "WER", r.wer)

r = score([ref], [hyp], "none@1")
print(r.profile_id, r.fingerprint, "CER", r.cer, "S/D/I", r.substitutions, r.deletions, r.insertions)
