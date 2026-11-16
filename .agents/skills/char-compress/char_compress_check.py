# ratios: loc_comments=158:7 imports_exports=7:11 calls_definitions=62:11
"""Executable guardrails for char-compress fixtures.

This is not a full natural-language compressor. It is a preservation checker
for the minimum fixture set declared in char-compress/fixtures.json.
It verifies that a simple deterministic skeleton keeps required flesh,
frozen bones, hmmm markers, and forbidden claim strings out of the output.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "char-compress" / "fixtures.json"

FROZEN_BONE_WORDS = {
    "not", "never", "no", "without", "only", "all", "none", "some", "any",
    "if", "unless", "except", "before", "after", "during", "until", "must",
    "may", "should", "cannot", "first", "second", "then", "last", "minus",
    "plus", "equals", "not-equals", "greater-than", "less-than", "public",
    "private", "secret", "experimental", "defended", "implemented",
    "test-backed", "EXPERIMENTAL", "DEFENDED", "IMPLEMENTED", "TEST-BACKED",
}

SAFE_BONE_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in",
    "on", "for", "and", "or", "but", "with", "as", "by", "from", "this",
    "that", "it", "its", "into", "around", "through", "while", "when",
}

TOKEN_RE = re.compile(
    r"[A-Za-z0-9_./:-]+|[≤≥!=]=|[+\-*/=<>]|[^\s]",
    re.UNICODE,
)
TRAILING_PUNCT = ".,;!?)]}”'\""
LEADING_PUNCT = "([{“'\""


@dataclass
class Failure:
    fixture_id: str
    message: str


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text)


def normalize_token(token: str) -> str:
    """Normalize punctuation while preserving paths, URLs, and dotted filenames."""
    token = token.strip()
    token = token.lstrip(LEADING_PUNCT)
    if re.search(r"\w[./:-]\w", token):
        return token.rstrip(TRAILING_PUNCT)
    return token.strip(LEADING_PUNCT + TRAILING_PUNCT)


def inventory_fingerprint(token: str) -> str:
    seen = set()
    out = []
    for ch in token:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return "".join(out)


def classify_token(token: str) -> str:
    stripped = normalize_token(token)
    if not stripped:
        return "dropped_bone"
    lowered = stripped.lower()

    if stripped == "hmmm" or lowered.startswith("hmmm"):
        return "hmmm"
    if stripped in FROZEN_BONE_WORDS or lowered in FROZEN_BONE_WORDS:
        return "frozen_bone"
    if re.search(r"\d", stripped):
        return "flesh"
    if "/" in stripped or "." in stripped or "-" in stripped or ":" in stripped:
        return "flesh"
    if lowered in SAFE_BONE_WORDS:
        return "dropped_bone"
    if re.fullmatch(r"\W+", stripped):
        return "dropped_bone"
    return "flesh"


def compress_text(text: str) -> Dict[str, Any]:
    skeleton: Dict[str, Any] = {
        "mode": "context-compression",
        "flesh": [],
        "frozen_bones": [],
        "hmmm": [],
        "dropped_bones": [],
        "fingerprints": {},
    }
    seen = {"flesh": set(), "frozen_bones": set(), "hmmm": set(), "dropped_bones": set()}

    for raw_token in tokenize(text):
        token = normalize_token(raw_token)
        cls = classify_token(raw_token)
        if cls == "flesh":
            key = token
            if key not in seen["flesh"]:
                seen["flesh"].add(key)
                skeleton["flesh"].append(key)
                skeleton["fingerprints"][key] = inventory_fingerprint(key)
        elif cls == "frozen_bone":
            key = token
            if key not in seen["frozen_bones"]:
                seen["frozen_bones"].add(key)
                skeleton["frozen_bones"].append(key)
                skeleton["fingerprints"][key] = inventory_fingerprint(key)
        elif cls == "hmmm":
            key = "hmmm"
            if key not in seen["hmmm"]:
                seen["hmmm"].add(key)
                skeleton["hmmm"].append(key)
        else:
            key = "safe connective scaffold"
            if key not in seen["dropped_bones"]:
                seen["dropped_bones"].add(key)
                skeleton["dropped_bones"].append(key)

    return skeleton


def contains_item(items: Sequence[str], expected: str) -> bool:
    expected_lower = expected.lower()
    return any(item == expected or item.lower() == expected_lower for item in items)


def skeleton_text(skeleton: Mapping[str, Any]) -> str:
    return json.dumps(skeleton, sort_keys=True)


def check_fixture(fixture: Mapping[str, Any]) -> List[Failure]:
    fixture_id = str(fixture.get("id", "<missing-id>"))
    text = str(fixture.get("text", ""))
    expected = fixture.get("expect", {})
    if not isinstance(expected, Mapping):
        expected = {}
    skeleton = compress_text(text)
    failures: List[Failure] = []

    for channel in ("flesh", "frozen_bones", "hmmm"):
        for expected_item in expected.get(channel, []):
            if not contains_item(skeleton.get(channel, []), str(expected_item)):
                failures.append(
                    Failure(
                        fixture_id,
                        f"missing {channel} item {expected_item!r}; got {skeleton.get(channel, [])!r}",
                    )
                )

    out = skeleton_text(skeleton)
    for forbidden in fixture.get("forbid_anywhere", []):
        if str(forbidden) in out:
            failures.append(Failure(fixture_id, f"forbidden string present: {forbidden!r}"))

    return failures


def load_fixtures(path: Path) -> List[Mapping[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fixtures = data.get("fixtures", [])
    if not isinstance(fixtures, list):
        raise ValueError(f"{path} has no fixtures list")
    return fixtures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run char-compress preservation fixtures.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result JSON.")
    args = parser.parse_args(argv)

    fixtures = load_fixtures(args.fixtures)
    failures: List[Failure] = []
    for fixture in fixtures:
        failures.extend(check_fixture(fixture))

    result = {
        "fixtures": len(fixtures),
        "failures": [failure.__dict__ for failure in failures],
        "status": "pass" if not failures else "fail",
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"char-compress fixtures: {result['status']} ({len(fixtures)} checked)")
        for failure in failures:
            print(f"FAIL {failure.fixture_id}: {failure.message}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
# ratios: loc_comments=158:7 imports_exports=7:11 calls_definitions=62:11
