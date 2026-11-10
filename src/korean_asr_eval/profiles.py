"""Normalization profiles: a name, an integer version and an ordered list of steps.

The *fingerprint* is the first 12 hex digits of the SHA-256 of the canonical JSON
of the step list. Two profiles with the same fingerprint normalize identically;
if you change a rule, the fingerprint changes, so numbers produced under
different rules cannot be mixed up unnoticed.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import steps as _steps
from .errors import ProfileFormatError, UnknownProfileError

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_TOML_KEYS = {"name", "version", "extends", "description", "replace", "steps"}


@dataclass(frozen=True)
class Step:
    """One normalization step: a registered name plus its (complete) parameters."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def make(cls, name: str, **params: Any) -> Step:
        """Build a step, validating parameters and filling in defaults."""
        return cls(name, _steps.canonical_params(name, params))

    def apply(self, text: str) -> str:
        return _steps.STEPS[self.name](text, **self.params)

    @property
    def label(self) -> str:
        """Short human label, e.g. ``kspon_dual(choose=phonetic)``."""
        shown = {k: v for k, v in self.params.items() if k != "pairs" and v != ""}
        if self.name == "replace":
            shown = {"pairs": len(self.params.get("pairs", []))}
        if not shown:
            return self.name
        return f"{self.name}(" + ", ".join(f"{k}={v}" for k, v in shown.items()) + ")"

    def to_json_obj(self) -> dict[str, Any]:
        return {"step": self.name, "params": self.params}


@dataclass(frozen=True)
class Profile:
    """A named, versioned, fingerprinted normalization recipe."""

    name: str
    version: int
    steps: tuple[Step, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise ProfileFormatError(
                f"invalid profile name {self.name!r}: use lowercase letters, digits, '-' or '_'"
            )
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise ProfileFormatError(
                f"invalid profile version {self.version!r} for {self.name!r}: use an integer >= 1"
            )

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            [s.to_json_obj() for s in self.steps],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    def describe(self) -> str:
        """One-line summary: id, fingerprint and the step labels."""
        chain = " > ".join(s.label for s in self.steps) or "(no steps)"
        return f"{self.id}  fp {self.fingerprint}  {chain}"


def _basic_tail() -> list[Step]:
    return [Step.make("lowercase"), Step.make("punct_to_space"), Step.make("collapse_spaces")]


def _kspon(choose: str) -> tuple[Step, ...]:
    return (
        Step.make("nfc"),
        Step.make("kspon_dual", choose=choose),
        Step.make("kspon_noise_tags"),
        Step.make("kspon_marks"),
        Step.make("percent_word", word="퍼센트"),
        *_basic_tail(),
    )


_BUILTINS: tuple[Profile, ...] = (
    Profile("none", 1, (Step.make("strip"),),
            "Trim the ends only; the 'no normalization' baseline (same as jiwer's cer_default)."),
    Profile("basic", 1, (Step.make("nfc"), *_basic_tail()),
            "NFC, lowercase, punctuation/symbols to spaces. Parentheses content is kept."),
    Profile("kspon-spelling", 1, _kspon("spelling"),
            "KsponSpeech transcript, spelling side of (spelling)/(pronunciation) pairs."),
    Profile("kspon-phonetic", 1, _kspon("phonetic"),
            "KsponSpeech transcript, pronunciation side of (spelling)/(pronunciation) pairs."),
)
_REGISTRY: dict[str, Profile] = {p.id: p for p in _BUILTINS}


def list_profiles() -> list[Profile]:
    """The built-in profiles, in a fixed order."""
    return list(_BUILTINS)


def get_profile(spec: str) -> Profile:
    """Look up a built-in profile by id, e.g. ``"kspon-phonetic@1"``.

    Raises:
        UnknownProfileError: the id (or its version) is not registered.
    """
    profile = _REGISTRY.get(spec)
    if profile is None:
        available = ", ".join(_REGISTRY)
        raise UnknownProfileError(
            f"unknown profile: {spec} (available: {available}; "
            f"for your own rules pass a .toml path, see load_profile)"
        )
    return profile


def resolve_profile(spec: str | Profile) -> Profile:
    """Accept a :class:`Profile`, a built-in id, or a path ending in ``.toml``."""
    if isinstance(spec, Profile):
        return spec
    if isinstance(spec, str) and spec.endswith(".toml"):
        return load_profile(spec)
    return get_profile(spec)


def load_profile(path: str | Path) -> Profile:
    """Load a user profile from a TOML file.

    Keys: ``name`` and ``version`` (required), ``extends`` (a built-in id),
    ``description``, ``[replace]`` (literal old = new table, applied right after
    the parent's ``nfc`` step so keys are matched against NFC text), and
    ``[[steps]]`` entries (``name`` plus step parameters) appended after the
    parent's steps.

    Raises:
        ProfileFormatError: unreadable file, unknown key, bad step or parameter.
        UnknownProfileError: ``extends`` names an unknown profile.
    """
    p = Path(path)
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise ProfileFormatError(f"cannot read profile file {p.name}: {exc.strerror}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ProfileFormatError(f"{p.name} is not valid TOML: {exc}") from exc

    unknown = sorted(set(data) - _TOML_KEYS)
    if unknown:
        raise ProfileFormatError(
            f"{p.name}: unknown key(s) {', '.join(unknown)}; allowed: {', '.join(sorted(_TOML_KEYS))}"
        )
    for key in ("name", "version"):
        if key not in data:
            raise ProfileFormatError(f"{p.name}: missing required key '{key}'")

    base: list[Step] = []
    if "extends" in data:
        base = list(get_profile(str(data["extends"])).steps)

    if "replace" in data:
        if not isinstance(data["replace"], dict):
            raise ProfileFormatError(f"{p.name}: [replace] must be a table of old = \"new\" strings")
        rep = Step.make("replace", pairs=data["replace"])
        at = 1 if base and base[0].name == "nfc" else 0
        base.insert(at, rep)

    for entry in data.get("steps", []):
        if not isinstance(entry, dict) or "name" not in entry:
            raise ProfileFormatError(f"{p.name}: each [[steps]] entry needs a 'name'")
        params = {k: v for k, v in entry.items() if k != "name"}
        base.append(Step.make(str(entry["name"]), **params))

    return Profile(
        name=str(data["name"]),
        version=data["version"],
        steps=tuple(base),
        description=str(data.get("description", "")),
    )

