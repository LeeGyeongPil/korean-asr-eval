"""Quick start: score two imaginary systems under three scoring rules.

Run with:  uv run python examples/quickstart.py
"""

import jiwer

from korean_asr_eval import compare, normalize, to_jiwer_transform

# One Kspon-style reference; the two systems write the number differently.
refs = {"u1": "o/ (70%)/(칠십 퍼센트) 정도는 b/ 음/ 됐어요+ n/"}
systems = {
    "says-words": {"u1": "칠십 퍼센트 정도는 음 됐어요."},
    "writes-digits": {"u1": "70퍼센트 정도는 음 됐어요."},
}

print(normalize(refs["u1"], "kspon-phonetic@1"))  # -> 칠십 퍼센트 정도는 음 됐어요

result = compare(refs, systems, ["none@1", "kspon-spelling@1", "kspon-phonetic@1"])
print(result.to_text())

# Already using jiwer? Add the profile as a transform and keep the rest of your code.
t = to_jiwer_transform("kspon-phonetic@1")
print(jiwer.cer(list(refs.values()), [systems["says-words"]["u1"]],
                reference_transform=t, hypothesis_transform=t))
