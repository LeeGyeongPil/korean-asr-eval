"""Use a profile inside existing jiwer code.

Run with:  uv run python examples/jiwer_transform.py
"""

import jiwer

from korean_asr_eval import score, to_jiwer_transform

refs = ["o/ (70%)/(칠십 퍼센트) 정도는 b/ 음/ 됐어요+ n/", "(3시)/(세 시)에 만나요"]
hyps = ["칠십 퍼센트 정도는 음 됐어요.", "3시에 만나요"]

t = to_jiwer_transform("kspon-phonetic@1")
print("jiwer  :", jiwer.cer(refs, hyps, reference_transform=t, hypothesis_transform=t))
print("score():", score(refs, hyps, "kspon-phonetic@1").cer)
