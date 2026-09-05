"""Findings schema for pubskill-lib.

The schema is a public contract. The CLI writes it and the fixture test
compares against it. Absence of a finding is not health.
"""

SCHEMA_VERSION = 1
TOOL = "pubskill-lib"

SURFACES = ("docs", "ci", "deps", "identity", "tests")
CLASSES = ("defect", "environment", "external", "policy", "hmmm")
OWNERS = ("repository", "environment", "external", "policy", "hmmm")


def new_document(source_pin, target_path):
    """Return an empty, schema-valid findings document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "source_pin": source_pin,
        "target": {
            "path": str(target_path),
            "commit": "hmmm",
            "remote": "hmmm",
            "dirty": False,
        },
        "surfaces": [],
        "findings": [],
        "hmmm": [],
    }


def validate_finding(finding):
    if not isinstance(finding, dict):
        raise ValueError("finding must be an object")
    for key in ("id", "surface", "claim", "evidence", "class", "owner"):
        if key not in finding:
            raise ValueError(f"finding missing key: {key}")
    if finding["surface"] not in SURFACES:
        raise ValueError(f"unknown surface: {finding['surface']}")
    if finding["class"] not in CLASSES:
        raise ValueError(f"unknown class: {finding['class']}")
    if finding["owner"] not in OWNERS:
        raise ValueError(f"unknown owner: {finding['owner']}")
    if not isinstance(finding.get("verified", False), bool):
        raise ValueError("verified must be boolean")
    return finding


def validate_document(document):
    if not isinstance(document, dict):
        raise ValueError("document must be an object")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if document.get("tool") != TOOL:
        raise ValueError("unsupported tool")
    if not isinstance(document.get("target"), dict):
        raise ValueError("target must be an object")
    for key in ("path", "commit", "remote"):
        if key not in document["target"]:
            raise ValueError(f"target missing key: {key}")
    if not isinstance(document.get("surfaces"), list):
        raise ValueError("surfaces must be a list")
    if not isinstance(document.get("findings"), list):
        raise ValueError("findings must be a list")
    for finding in document["findings"]:
        validate_finding(finding)
    if not isinstance(document.get("hmmm"), list):
        raise ValueError("hmmm must be a list")
    return document
