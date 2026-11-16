"""Fail-closed fill-in generator: python -m unittest discover -s tests."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from pubskill_lib import fill

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
EXAMPLE = TEMPLATES / "example-skill" / "example.config.json"


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "pubskill_lib.fill", *args],
        capture_output=True, text=True, check=False,
    )


class FillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def config(self, data, suffix=".json"):
        path = self.tmp / f"config{suffix}"
        path.write_text(json.dumps(data) if suffix == ".json" else data)
        return path

    def templates_copy(self):
        root = self.tmp / "templates"
        shutil.copytree(TEMPLATES, root)
        return root

    def test_repository_templates_verify(self):
        result = run("--verify", "--templates", str(TEMPLATES))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_org_templates_ship_yet(self):
        self.assertEqual(fill.list_templates(TEMPLATES), ["example-skill"])
        self.assertFalse(list((ROOT / ".agents" / "skills").glob("**/*.tmpl")))

    def test_missing_and_empty_fields_list_every_field_without_values(self):
        cfg = self.config({"org_name": "   "})
        result = run("example-skill", "--config", str(cfg), "--out", str(self.tmp / "out"), "--templates", str(TEMPLATES))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field: catalog_repo", result.stderr)
        self.assertIn("empty field: org_name", result.stderr)
        self.assertFalse((self.tmp / "out").exists())

    def test_unused_config_key_is_error_and_value_is_not_printed(self):
        cfg = self.config({"org_name": "ExampleOrg", "catalog_repo": "ExampleOrg/x", "api_token": "sk-FAKE-do-not-print"})
        result = run("example-skill", "--config", str(cfg), "--out", str(self.tmp / "out"), "--templates", str(TEMPLATES))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unused config key: api_token", result.stderr)
        self.assertNotIn("sk-FAKE", result.stderr + result.stdout)
        self.assertFalse((self.tmp / "out").exists())

    def test_unknown_and_malformed_placeholders_fail(self):
        root = self.templates_copy()
        skill = root / "example-skill" / "files" / "SKILL.md.tmpl"
        skill.write_text(skill.read_text() + "\n{{pubskill:not_declared}}\n{{pubskill: org_name}}\n")
        with self.assertRaises(fill.FillError) as caught:
            fill.load_template(root, "example-skill")
        text = "\n".join(caught.exception.problems)
        self.assertIn("unknown placeholder not_declared", text)
        self.assertIn("malformed placeholder", text)

    def test_declared_but_unused_field_fails(self):
        root = self.templates_copy()
        spec_path = root / "example-skill" / "template.json"
        spec = json.loads(spec_path.read_text())
        spec["fields"]["extra"] = {"description": "never used", "required": True}
        spec_path.write_text(json.dumps(spec))
        with self.assertRaises(fill.FillError) as caught:
            fill.load_template(root, "example-skill")
        self.assertIn("declared field extra is never used", "\n".join(caught.exception.problems))

    def test_leak_gate_flags_org_strings_without_false_positives(self):
        root = self.templates_copy()
        skill = root / "example-skill" / "files" / "SKILL.md.tmpl"
        clean = skill.read_text()
        self.assertEqual(fill.leak_scan(root, "example-skill"), [])
        skill.write_text(clean + "\nSee pubskill-lib and digest 3a0f; the A0 cli.\n")
        hits = fill.leak_scan(root, "example-skill")
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("'a0'", hits[0])
        skill.write_text(clean + "\nCopied from The-Interdependency/skill-lib.\n")
        terms = "\n".join(fill.leak_scan(root, "example-skill"))
        self.assertIn("'interdependency'", terms)
        self.assertIn("'skill-lib'", terms)
        self.assertTrue(any("org-specific" in p for p in fill.verify(root)))

    def test_lock_records_template_hash(self):
        root = self.templates_copy()
        (root / "example-skill" / "files" / "SKILL.md.tmpl").write_text("{{pubskill:org_name}} {{pubskill:catalog_repo}} {{pubskill:escalation_contact}}\n")
        self.assertTrue(any("template_sha256 drift" in p for p in fill.verify(root)))

    def test_output_is_deterministic_and_toml_matches_json(self):
        a, b = self.tmp / "a", self.tmp / "b"
        toml = self.config('org_name = "ExampleOrg"\ncatalog_repo = "ExampleOrg/example-skills"\n', ".toml")
        for out, cfg in ((a, EXAMPLE), (b, toml)):
            result = run("all", "--config", str(cfg), "--out", str(out), "--templates", str(TEMPLATES))
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(fill._read_tree(a), fill._read_tree(b))
        text = (a / "example-skill" / "SKILL.md").read_text()
        self.assertIn("ExampleOrg/example-skills", text)
        self.assertIn("the repository maintainers", text)
        self.assertNotIn("{{pubskill", text)

    def test_check_reports_drift_and_writes_nothing(self):
        out = self.tmp / "out"
        args = ("example-skill", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(TEMPLATES))
        self.assertNotEqual(run(*args, "--check").returncode, 0)
        self.assertFalse(out.exists())
        self.assertEqual(run(*args).returncode, 0)
        self.assertEqual(run(*args, "--check").returncode, 0)
        (out / "example-skill" / "SKILL.md").write_text("hand edit\n")
        result = run(*args, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("SKILL.md", result.stderr)

    def test_refuses_to_overwrite_different_content_without_force(self):
        out = self.tmp / "out"
        args = ("example-skill", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(TEMPLATES))
        self.assertEqual(run(*args).returncode, 0)
        self.assertEqual(run(*args).returncode, 0)  # identical content is a no-op
        target = out / "example-skill" / "SKILL.md"
        target.write_text("local edit\n")
        result = run(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--force", result.stderr)
        self.assertEqual(target.read_text(), "local edit\n")
        self.assertEqual(run(*args, "--force").returncode, 0)
        self.assertNotEqual(target.read_text(), "local edit\n")
        self.assertEqual(run(*args, "--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
