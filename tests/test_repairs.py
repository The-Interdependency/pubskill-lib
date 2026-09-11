"""Regression tests for audit findings repaired on 2026-09-10."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pubskill_lib import audit, evidence, examine, msdmd_writer, narrative, providers, ratios


class CredentialBoundaryTests(unittest.TestCase):
    def test_dotenv_cannot_override_provider_base_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "OPENAI_API_KEY=repo-key\nOPENAI_BASE_URL=https://attacker.invalid/v1\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "operator-key"}, clear=True):
                merged = providers.env_with_dotenv(env_file)
            self.assertEqual("operator-key", merged["OPENAI_API_KEY"])
            self.assertNotIn("OPENAI_BASE_URL", merged)

    def test_process_environment_may_set_base_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("OPENAI_BASE_URL=https://attacker.invalid/v1\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "operator-key",
                    "OPENAI_BASE_URL": "https://operator.example/v1",
                },
                clear=True,
            ):
                merged = providers.env_with_dotenv(env_file)
            self.assertEqual("https://operator.example/v1", merged["OPENAI_BASE_URL"])

    def test_blank_model_override_uses_provider_default(self):
        openai = providers.OpenAIProvider({"OPENAI_API_KEY": "key", "OPENAI_MODEL": ""})
        anthropic = providers.AnthropicProvider({"ANTHROPIC_API_KEY": "key", "ANTHROPIC_MODEL": ""})
        self.assertEqual(openai.default_model(), openai.model)
        self.assertEqual(anthropic.default_model(), anthropic.model)


class NarrativeBoundaryTests(unittest.TestCase):
    def test_narrative_preserves_python_shebang_and_encoding_header(self):
        text = (
            "#!/usr/bin/env python3\n"
            "# -*- coding: latin-1 -*-\n"
            "# ratios: loc_comments=1:1 imports_exports=0:0 calls_definitions=1:0\n"
            "print('hi')\n"
            "# ratios: loc_comments=1:1 imports_exports=0:0 calls_definitions=1:0\n"
        )
        entry = {
            "id": "examiner_abc",
            "summary": "Prints hi.",
            "evidence_sha256": "abc",
            "model": "none",
            "provider": "none",
            "generated_at": "now",
            "stale": "false",
        }
        new, changed = msdmd_writer.upsert_narrative(text, "#", entry, Path("tool.py"))
        lines = new.splitlines()
        self.assertTrue(changed)
        self.assertTrue(lines[0].startswith("#!"))
        self.assertIn("coding:", lines[1])
        self.assertTrue(lines[2].startswith("# ratios:"))
        self.assertEqual("# === NARRATIVE ===", lines[3])

    def test_successful_narrative_records_model(self):
        class FakeProvider:
            name = "fake"
            model = "model-1"

            def chat(self, system, user):
                return "Does one thing."

        ev = evidence.FileEvidence(path="x.py", language="py", marker="#", sha256="abc")
        result = narrative.narrate_file(ev, "print('x')\n", [FakeProvider()], "now")
        self.assertEqual("fake", result.entry["provider"])
        self.assertEqual("model-1", result.entry["model"])

    def test_generated_narrative_does_not_change_ratios(self):
        class FakeProvider:
            name = "fake"
            model = "model-1"

            def chat(self, system, user):
                return "Generated prose mentions fake_call() and comments."

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "x.py"
            original = "print('x')\n"
            path.write_text(original, encoding="utf-8")
            ev = evidence.read_evidence(root, path)
            expected = ratios.RatiosEngine().compute(path, original)
            examine._apply(root, [ev], [FakeProvider()], True)
            written = evidence.read_evidence(root, path)
            self.assertTrue(written.ratios_lines)
            for key, value in expected.items():
                self.assertIn(f"{key}={value}", written.ratios_lines[0])

    def test_apply_skips_parser_supported_language_without_safe_ratio_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "index.php"
            original = "<?php\necho 'ok';\n"
            path.write_text(original, encoding="utf-8")
            ev = evidence.read_evidence(root, path)
            self.assertIsNotNone(ev.marker)
            _, report = examine._apply(root, [ev], [], False)
            self.assertEqual(original, path.read_text(encoding="utf-8"))
            self.assertEqual([], report["changed"])


class CanonicalMarkerTests(unittest.TestCase):
    def test_evidence_uses_vendored_msdmd_registry(self):
        markers = evidence._comment_markers()
        self.assertEqual("#", markers[".py"])
        self.assertEqual("//", markers[".ts"])
        self.assertIn(".ps1", markers)


class PackageScriptTests(unittest.TestCase):
    def test_missing_local_package_script_is_a_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "node scripts/build.js"}}),
                encoding="utf-8",
            )
            document = audit.audit_path(root, "pin")
            findings = [f for f in document["findings"] if f["surface"] == "deps"]
            self.assertEqual(1, len(findings))
            self.assertIn("scripts/build.js", findings[0]["claim"])

    def test_existing_local_package_script_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "build.js").write_text("console.log('ok')\n", encoding="utf-8")
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "node scripts/build.js"}}),
                encoding="utf-8",
            )
            document = audit.audit_path(root, "pin")
            self.assertFalse([f for f in document["findings"] if f["surface"] == "deps"])

    def test_interpreter_flags_do_not_hide_missing_local_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {
                    "node": "node --trace-warnings missing.js",
                    "python": "python -u missing.py",
                    "shell": "bash -e missing.sh",
                }}),
                encoding="utf-8",
            )
            document = audit.audit_path(root, "pin")
            claims = [f["claim"] for f in document["findings"] if f["surface"] == "deps"]
            self.assertTrue(any("missing.js" in claim for claim in claims))
            self.assertTrue(any("missing.py" in claim for claim in claims))
            self.assertTrue(any("missing.sh" in claim for claim in claims))

    def test_non_object_package_manifest_is_target_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("[]\n", encoding="utf-8")
            document = audit.audit_path(root, "pin")
            claims = [f["claim"] for f in document["findings"] if f["surface"] == "deps"]
            self.assertIn("package.json top level is not an object", claims)


if __name__ == "__main__":
    unittest.main()
