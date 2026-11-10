"""korean-asr-eval: pin the normalization rules behind Korean ASR error rates.

Distances and S/D/I counts come from jiwer; this package adds named, versioned,
fingerprinted normalization profiles and reports how much a profile changes
scores and model rankings.
"""

from ._version import package_version as _package_version
from .compare import Comparison, RankFlip, UttChange, compare
from .errors import (
    EmptyReferenceWarning,
    IdMismatchError,
    InputFormatError,
    KoreanAsrEvalError,
    ProfileFormatError,
    UnknownProfileError,
)
from .io import read_pairs
from .jiwer_compat import to_jiwer_transform
from .normalize import TraceStep, normalize, normalize_trace
from .profiles import Profile, Step, get_profile, list_profiles, load_profile
from .scoring import Score, UttScore, score

__version__ = _package_version()

__all__ = [
    "Comparison",
    "EmptyReferenceWarning",
    "IdMismatchError",
    "InputFormatError",
    "KoreanAsrEvalError",
    "Profile",
    "ProfileFormatError",
    "RankFlip",
    "Score",
    "Step",
    "TraceStep",
    "UnknownProfileError",
    "UttChange",
    "UttScore",
    "__version__",
    "compare",
    "get_profile",
    "list_profiles",
    "load_profile",
    "normalize",
    "normalize_trace",
    "read_pairs",
    "score",
    "to_jiwer_transform",
]
