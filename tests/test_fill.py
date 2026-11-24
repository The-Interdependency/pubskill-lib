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

    def templates_copy(self, name="templates"):
        root = self.tmp / name
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


    def second_template(self, root, required_contact):
        other = root / "other-skill"
        shutil.copytree(root / "example-skill", other)
        spec = json.loads((other / "template.json").read_text())
        spec["name"] = "other-skill"
        contact = {"description": "Who decides when the skill hits an unknown", "required": required_contact}
        if not required_contact:
            contact["default"] = "a different default"
        spec["fields"]["escalation_contact"] = contact
        (other / "template.json").write_text(json.dumps(spec))
        return other

    def test_all_rejects_conflicting_shared_field_declarations(self):
        root = self.templates_copy()
        self.second_template(root, required_contact=True)
        out = self.tmp / "out"
        result = run("all", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicting declarations for field escalation_contact", result.stderr)
        self.assertFalse(out.exists())
        self.assertTrue(any("conflicting declarations" in p for p in fill.verify(root)))

    def test_all_rejects_conflicting_shared_defaults(self):
        root = self.templates_copy()
        self.second_template(root, required_contact=False)
        out = self.tmp / "out"
        result = run("all", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicting declarations for field escalation_contact", result.stderr)
        self.assertFalse(out.exists())

    def test_defaults_cannot_carry_placeholder_syntax(self):
        for index, default in enumerate(("{{pubskill:org_name}}", "{{pubskill:undeclared}}", "{{pubskill: broken", "two\nlines", 7)):
            with self.subTest(default=default):
                root = self.templates_copy(f"templates-{index}")
                spec_path = root / "example-skill" / "template.json"
                spec = json.loads(spec_path.read_text())
                spec["fields"]["escalation_contact"]["default"] = default
                spec_path.write_text(json.dumps(spec))
                with self.assertRaises(fill.FillError) as caught:
                    fill.load_template(root, "example-skill")
                self.assertIn("escalation_contact", "\n".join(caught.exception.problems))
                self.assertTrue(any("escalation_contact" in p for p in fill.verify(root)))

    def test_force_preflights_every_target_before_writing(self):
        root = self.templates_copy()
        self.second_template(root, required_contact=False)
        spec_path = root / "other-skill" / "template.json"
        spec = json.loads(spec_path.read_text())
        spec["fields"]["escalation_contact"]["default"] = "the repository maintainers"
        spec_path.write_text(json.dumps(spec))
        decoy = self.tmp / "decoy"
        decoy.mkdir()
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind):
                out = self.tmp / f"out-{kind}"
                args = ("all", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
                self.assertEqual(run(*args).returncode, 0)
                first = out / "example-skill" / "SKILL.md"
                first.write_text("local edit\n")
                shutil.rmtree(out / "other-skill")
                if kind == "file":
                    (out / "other-skill").write_text("not a directory\n")
                else:
                    (out / "other-skill").symlink_to(decoy, target_is_directory=True)
                result = run(*args, "--force")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(first.read_text(), "local edit\n")
                self.assertEqual(list(decoy.iterdir()), [])

    def test_placeholder_default_refuses_fill_and_writes_nothing(self):
        # Codex r4589674599: an undeclared placeholder in a default must not be
        # written verbatim into the consumer copy by the single render pass.
        root = self.templates_copy()
        spec_path = root / "example-skill" / "template.json"
        spec = json.loads(spec_path.read_text())
        spec["fields"]["escalation_contact"]["default"] = "{{pubskill:undeclared}}"
        spec_path.write_text(json.dumps(spec))
        out = self.tmp / "out"
        for name in ("example-skill", "all"):
            with self.subTest(name=name):
                result = run(name, "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("must not contain placeholder syntax", result.stderr)
                self.assertFalse(out.exists())

    def test_template_directory_without_schema_is_reported_not_skipped(self):
        # Codex r4589901488: a template dir missing or misnaming template.json
        # must fail --verify and `all`, not vanish from the gate.
        for variant in ("missing", "misnamed"):
            with self.subTest(variant=variant):
                root = self.templates_copy(f"templates-{variant}")
                stray = root / "new-org-skill"
                (stray / "files").mkdir(parents=True)
                (stray / "files" / "SKILL.md.tmpl").write_text("{{pubskill:undeclared}} for skill-lib\n")
                if variant == "misnamed":
                    (stray / "Template.json").write_text("{}")
                self.assertIn("new-org-skill", fill.list_templates(root))
                problems = fill.verify(root)
                self.assertIn("new-org-skill: missing template.json schema", problems)
                result = run("--verify", "--templates", str(root))
                self.assertEqual(result.returncode, 1)
                self.assertIn("new-org-skill: missing template.json schema", result.stderr)
                out = self.tmp / f"out-{variant}"
                result = run("all", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
                self.assertEqual(result.returncode, 2)
                self.assertIn("new-org-skill: missing template.json schema", result.stderr)
                self.assertFalse(out.exists())
                result = run("new-org-skill", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
                self.assertEqual(result.returncode, 2)
                self.assertIn("new-org-skill: missing template.json schema", result.stderr)

    def test_symlinked_template_directory_is_rejected(self):
        root = self.templates_copy()
        (root / "linked-skill").symlink_to(root / "example-skill", target_is_directory=True)
        self.assertIn("linked-skill: template directory must not be a symlink", fill.verify(root))

    def compatible_second_template(self, root):
        other = self.second_template(root, required_contact=False)
        spec_path = other / "template.json"
        spec = json.loads(spec_path.read_text())
        spec["fields"]["escalation_contact"]["default"] = "the repository maintainers"
        spec_path.write_text(json.dumps(spec))
        return other

    def assert_layout_refused(self, extra_files, expected):
        # The broken layout lives in other-skill, which `all` fills after
        # example-skill: nothing may be published before the refusal.
        root = self.templates_copy(f"templates-{len(list(self.tmp.iterdir()))}")
        other = self.compatible_second_template(root)
        for rel, text in extra_files.items():
            path = other / "files" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        problems = "\n".join(fill.verify(root))
        self.assertIn(expected, problems)
        with self.assertRaises(fill.FillError):
            fill.load_template(root, "other-skill")
        out = self.tmp / f"out-{root.name}"
        result = run("all", "--config", str(EXAMPLE), "--out", str(out), "--templates", str(root))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(expected, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(out.exists())

    def test_rendered_file_directory_collision_is_refused(self):
        # Codex r4683043077: files/docs.tmpl renders a file `docs` while
        # files/docs/README.md.tmpl needs `docs/` to be a directory.
        self.assert_layout_refused(
            {"docs.tmpl": "plain\n", "docs/README.md.tmpl": "plain\n"},
            "rendered file docs (from docs.tmpl) is also a directory for docs/README.md",
        )
        self.assert_layout_refused(
            {"a/b.tmpl": "plain\n", "a/b/c/d.md.tmpl": "plain\n"},
            "rendered file a/b (from a/b.tmpl) is also a directory for a/b/c/d.md",
        )

    def test_reserved_provenance_name_is_refused(self):
        for files in ({"FILLED_FROM.json.tmpl": "{}\n"}, {"FILLED_FROM.json/x.md.tmpl": "plain\n"}):
            with self.subTest(files=sorted(files)):
                self.assert_layout_refused(files, "collides with reserved FILLED_FROM.json")

    def test_empty_rendered_name_is_refused(self):
        for rel in (".tmpl", "docs/.tmpl"):
            with self.subTest(rel=rel):
                self.assert_layout_refused({rel: "plain\n"}, f"template file has an empty rendered name: {rel}")

    def test_malformed_template_json_is_reported_not_raised(self):
        for index, raw in enumerate(("{not json", "[]", b"\xff\xfe")):
            with self.subTest(raw=raw):
                root = self.templates_copy(f"templates-json-{index}")
                spec_path = root / "example-skill" / "template.json"
                if isinstance(raw, bytes):
                    spec_path.write_bytes(raw)
                else:
                    spec_path.write_text(raw)
                problems = fill.verify(root)
                self.assertTrue(any(p.startswith("example-skill: template.json") for p in problems), problems)
                result = run("--verify", "--templates", str(root))
                self.assertEqual(result.returncode, 1)
                self.assertIn("example-skill: template.json", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
