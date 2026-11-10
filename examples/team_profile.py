"""Load a team profile from TOML.

Run with:  uv run python examples/team_profile.py
"""

from pathlib import Path

from korean_asr_eval import load_profile, normalize

profile = load_profile(Path(__file__).with_name("my-lab.toml"))
print(profile.id, profile.fingerprint)

text = "三十 명, 5㎏ 입니다"
print(normalize(text, profile))
print(normalize(text, "basic@1"))
