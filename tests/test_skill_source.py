"""Replay the pinned public slice: python -m unittest discover -s tests.

These tests bind provenance and exercise the shipped Python native reader without
executing inspected code. Cross-repository byte identity is checked separately
by the canonical-source CI job. No remote service or provider key is needed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from pubskill_lib import _msdmd_universal
from pubskill_lib.audit import _read_source_pin

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"


class SkillSourceTests(unittest.TestCase):
    def test_pin_agrees_across_installed_package_and_source_documents(self):
        pin = _read_source_pin()
        self.assertRegex(pin, r"^[0-9a-f]{40}$")
        source = json.loads((ROOT / "src/pubskill_lib/_source.json").read_text())
        self.assertEqual(source["commit"], pin)
        text = (ROOT / "SOURCE.md").read_text()
        self.assertEqual(re.search(r"Pinned SHA \| `([0-9a-f]{40})`", text)[1], pin)
        text = (SKILLS / "README.md").read_text()
        self.assertEqual(re.search(r"Source commit: `([0-9a-f]{40})`", text)[1], pin)

    def test_packaged_parser_is_exact_canonical_vendored_copy(self):
        self.assertEqual(
            Path(_msdmd_universal.__file__).read_bytes(),
            (SKILLS / "msdmd/parsers/universal.py").read_bytes(),
        )

    def test_installed_skills_match_pinned_producer_index(self):
        index = json.loads((SKILLS / "skills.json").read_text(encoding="utf-8"))
        expected = {entry["name"] for entry in index["skills"]}
        self.assertEqual(len(expected), 44)
        installed = {
            path.parent.name
            for path in SKILLS.glob("*/SKILL.md")
            if path.parent.name != "doctrine"
        }
        self.assertEqual(installed, expected)
        for entry in index["skills"]:
            self.assertEqual(entry["path"], f"{entry['name']}/SKILL.md")
            self.assertTrue((SKILLS / entry["name"] / "SKILL.md").is_file())

    def test_catalog_manifest_replays_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "catalog.json"
            command = [
                sys.executable,
                str(ROOT / "tools" / "build_catalog.py"),
                "--out",
                str(out),
            ]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(out.read_bytes(), (SKILLS / "catalog.json").read_bytes())

    def test_catalog_binds_every_skill_to_source_commit_and_digest(self):
        index = json.loads((SKILLS / "skills.json").read_text(encoding="utf-8"))
        catalog = json.loads((SKILLS / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema"], "pubskill-lib.catalog")
        self.assertEqual(catalog["version"], 1)
        self.assertEqual(catalog["producer"]["commit"], _read_source_pin())
        self.assertEqual(catalog["skill_count"], len(index["skills"]))
        by_name = {item["name"]: item for item in catalog["skills"]}
        self.assertEqual(set(by_name), {entry["name"] for entry in index["skills"]})
        for entry in index["skills"]:
            item = by_name[entry["name"]]
            self.assertEqual(item["source_commit"], _read_source_pin())
            self.assertRegex(item["digest"], r"^[0-9a-f]{64}$")
            self.assertEqual(item["kind"], entry.get("kind"))
            self.assertEqual(item["status"], entry.get("status"))
            self.assertEqual(item["path"], entry["path"])

    def test_parity_gate_fails_when_vendored_skill_bytes_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "skills"
            shutil.copytree(SKILLS, install)
            target = install / "msdmd" / "SKILL.md"
            target.write_text(
                target.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8"
            )
            out = root / "catalog.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "build_catalog.py"),
                    "--skills-root",
                    str(install),
                    "--source-json",
                    str(ROOT / "src" / "pubskill_lib" / "_source.json"),
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            mutated = json.loads(out.read_text(encoding="utf-8"))
            committed = json.loads((SKILLS / "catalog.json").read_text(encoding="utf-8"))
            self.assertNotEqual(
                mutated["propagated_set_digest"], committed["propagated_set_digest"]
            )

    def test_parity_gate_fails_on_removed_or_added_producer_skills(self):
        source_json = ROOT / "src" / "pubskill_lib" / "_source.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            removed_root = root / "removed"
            shutil.copytree(SKILLS, removed_root)
            shutil.rmtree(removed_root / "msdmd")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "build_catalog.py"),
                    "--skills-root",
                    str(removed_root),
                    "--source-json",
                    str(source_json),
                    "--out",
                    str(root / "removed-catalog.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing SKILL.md", result.stderr)

            added_root = root / "added"
            shutil.copytree(SKILLS, added_root)
            (added_root / "not-in-producer-index").mkdir()
            (added_root / "not-in-producer-index" / "SKILL.md").write_text(
                "---\nname: not-in-producer-index\ndescription: drift\n---\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "build_catalog.py"),
                    "--skills-root",
                    str(added_root),
                    "--source-json",
                    str(source_json),
                    "--out",
                    str(root / "added-catalog.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not present in producer index", result.stderr)

    def test_work_graph_is_bound_to_pin(self):
        graph = json.loads((ROOT / "docs/work-graphs/skill-source-sync.json").read_text())
        self.assertEqual(graph["schema"], "the-interdependency.stack-manifest")
        self.assertEqual(graph["version"], "1.0.0")
        payload = {key: graph[key] for key in ("repositories", "boundaries")}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(graph["work_graph_sha256"], digest)
        producer = next(item for item in graph["repositories"] if item["repository"] == "The-Interdependency/skill-lib")
        self.assertEqual(producer["commit"], _read_source_pin())
        self.assertFalse(graph["boundaries"]["authority_transfer"])
        self.assertTrue(graph["boundaries"]["hmmm"])

    def test_native_reader_does_not_execute_source_and_detects_staleness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            sentinel = root / "executed"
            source = target / "example.py"
            original = (
                f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n"
                "def double(value: int) -> int:\n"
                "    \"\"\"Return twice the supplied value.\"\"\"\n"
                "    return value * 2\n"
            ).encode()
            source.write_bytes(original)
            output = root / "projection"
            env = dict(os.environ, PYTHONPATH=str(SKILLS))
            command = [sys.executable, "-m", "msdmd.module_projection", "--root", str(target),
                       "--repo", "fixture/native", "--revision", "fixture-v1", "--out-dir", str(output)]
            def run(mode):
                return subprocess.run(command + [mode], cwd=root, env=env, capture_output=True, text=True)
            result = run("--write")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(sentinel.exists(), "collector executed inspected application")
            projections = list(output.rglob("*.jsonl"))
            self.assertEqual(len(projections), 1)
            records = [json.loads(line) for line in projections[0].read_text().splitlines()]
            self.assertEqual(records[0]["source_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(records[0]["source_revision"], "fixture-v1")
            self.assertTrue(any(item.get("record_type") == "symbol" and item.get("qualified_name") == "double"
                                and item.get("standing") == "syntactically_observed" for item in records))
            self.assertTrue(any(item.get("record_type") == "metadata" and "Return twice" in item.get("text", "") for item in records))
            result = run("--check")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            source.write_bytes(original.replace(b"value * 2", b"value * 3"))
            result = run("--check")
            self.assertNotEqual(result.returncode, 0, "stale source incorrectly passed byte replay")
            self.assertFalse(sentinel.exists())
