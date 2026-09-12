"""Regression tests for audit findings repaired on 2026-09-10."""

import hashlib
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
    def test_fence_shaped_literal_data_remains_source(self):
        class FakeProvider:
            name, model = "fake", "model-1"
            def chat(self, system, user):
                return "Stores a literal string."

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "literal.py"
            original = 'payload = """\n# === NARRATIVE ===\n# id: literal_data\n# summary: alpha\n# === END NARRATIVE ===\n# ratios: loc_comments=1:2 imports_exports=3:4 calls_definitions=5:6\n"""\n'
            path.write_text(original)
            before = evidence.read_evidence(root, path)
            self.assertEqual([], before.narrative_entries)
            path.write_text(original.replace("alpha", "beta"))
            self.assertNotEqual(before.sha256, evidence.read_evidence(root, path).sha256)
            path.write_text(original)
            examine._apply(root, [before], [FakeProvider()], True)
            namespace = {}
            exec(compile(path.read_bytes(), str(path), "exec"), namespace)
            expected = {}
            exec(compile(original, str(path), "exec"), expected)
            self.assertEqual(expected["payload"], namespace["payload"])
            after = evidence.read_evidence(root, path)
            self.assertEqual(before.sha256, after.sha256)
            self.assertEqual(1, len(after.narrative_entries))
            first = path.read_bytes()
            examine._apply(root, [after], [], False)
            self.assertEqual(first, path.read_bytes())

    def test_provider_cannot_overwrite_a_concurrent_source_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "concurrent.py"
            path.write_text("print('old')\n")
            concurrent = b"print('concurrent edit')\n"
            class EditingProvider:
                name, model = "fake", "model-1"
                def chat(self, system, user):
                    path.write_bytes(concurrent)
                    return "Prints old."
            _, report = examine._apply(root, [evidence.read_evidence(root, path)], [EditingProvider()], True)
            self.assertEqual(concurrent, path.read_bytes())
            self.assertEqual([], report["changed"])
            self.assertIn("concurrent.py", report["hmmm"])

    def test_conditional_publication_preserves_competing_writes(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            original = b"original\n"
            concurrent = b"concurrent\n"
            path.write_bytes(original)
            link = os.link
            def competing_write(source, target, **kwargs):
                if Path(source).name == "candidate" and Path(target) == path:
                    path.write_bytes(concurrent)
                return link(source, target, **kwargs)
            with patch("pubskill_lib.msdmd_writer.os.link", side_effect=competing_write):
                with self.assertRaises(msdmd_writer.SourceChangedError):
                    msdmd_writer.write_text_safely(path, "new\n", expected_raw=original)
            self.assertEqual(concurrent, path.read_bytes())
            self.assertEqual([original], [p.read_bytes() for p in Path(tmp).glob(".examiner-originals-*/original")])

    def test_failed_publication_preserves_source_and_external_hardlinks(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            original = b"original\n"
            path.write_bytes(original)
            alias = Path(tmp) / "external.py"
            alias.hardlink_to(path)
            link = os.link
            def fail_candidate(source, target, **kwargs):
                if Path(source).name == "candidate" and Path(target) == path:
                    raise OSError("publication failed")
                return link(source, target, **kwargs)
            with patch("pubskill_lib.msdmd_writer.os.link", side_effect=fail_candidate):
                with self.assertRaises(OSError):
                    msdmd_writer.write_text_safely(path, "new\n", expected_raw=original)
            self.assertEqual(original, path.read_bytes())
            with path.open("r+b") as writer:
                recovery = msdmd_writer.write_text_safely(path, "new\n", expected_raw=original)
                writer.write(b"late edit")
                writer.truncate()
            self.assertEqual(b"late edit", recovery.read_bytes())
            self.assertEqual(b"late edit", alias.read_bytes())
            self.assertEqual(b"new\n", path.read_bytes())

    def test_unrelated_similarly_named_source_is_not_canonical_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("other/pubskill_lib/_msdmd_universal.py", "src/pubskill_lib/_msdmd_universal.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("print('ordinary user code')\n")
                item = evidence.read_evidence(root, path)
                self.assertEqual(1, examine._plan(root, [item])["supported_files"])
                _, report = examine._apply(root, [item], [], False)
                self.assertTrue(report["changed"])
                self.assertEqual([], report["preserved_authority"])

    def test_candidate_setup_failure_cleans_recovery_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            path.write_text("original\n")
            for operation in ("write_bytes", "chmod"):
                with patch.object(Path, operation, side_effect=OSError("quota")):
                    with self.assertRaises(OSError):
                        msdmd_writer.write_text_safely(path, "new\n")
                self.assertEqual("original\n", path.read_text())
                self.assertEqual([], list(Path(tmp).glob(".examiner-originals-*")))

    def test_publication_preserves_inode_metadata_or_refuses_to_move(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            path.write_text("original\n")
            path.chmod(0o751)
            os.setxattr(path, "user.pubskill_test", b"retained")
            original_metadata = msdmd_writer._inode_metadata(path)
            msdmd_writer.write_text_safely(path, "new\n")
            self.assertEqual(original_metadata, msdmd_writer._inode_metadata(path))
            with patch("pubskill_lib.msdmd_writer.os.setxattr", side_effect=OSError("metadata denied")):
                with self.assertRaises(OSError):
                    msdmd_writer.write_text_safely(path, "third\n")
            self.assertEqual("new\n", path.read_text())
            self.assertEqual(original_metadata, msdmd_writer._inode_metadata(path))

    def test_assembled_narrative_is_stale_after_preserving_concurrent_edit(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "source.py"
            original = "print('old')\n"
            path.write_text(original)
            ev = evidence.read_evidence(root, path)
            decorated, _ = msdmd_writer.upsert_narrative(original, "#", {"id": "old_narrative", "summary": "Old summary", "evidence_sha256": ev.sha256}, path)
            path.write_text(decorated)
            class EditingProvider:
                name, model = "fake", "model"
                def chat(self, system, user):
                    path.write_text(path.read_text().replace("print('old')", "print('edited')"))
                    return "Generated stale summary"
            with patch("pubskill_lib.providers.configured_providers", return_value=[EditingProvider()]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, examine.main(["--repo", str(root), "--apply", "--narrate"]))
            output = (root / "docs/examiner/EXAMINER.md").read_text()
            self.assertIn("Old summary", output)
            self.assertIn("> stale:", output)
            self.assertIn("print('edited')", path.read_text())

    def test_apply_preserves_packaged_canonical_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parser = root / "src/pubskill_lib/_msdmd_universal.py"
            parser.parent.mkdir(parents=True)
            original = Path(evidence._canonical_msdmd.__file__).read_bytes()
            parser.write_bytes(original)
            ev = evidence.read_evidence(root, parser)
            _, report = examine._apply(root, [ev], [], True)
            self.assertEqual(original, parser.read_bytes())
            self.assertEqual([], report["changed"])
            self.assertEqual([ev.path], report["preserved_authority"])
            self.assertEqual(0, examine._plan(root, [ev])["supported_files"])

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
            self.assertIn("index.php", report["hmmm"])
            self.assertEqual(0, examine._plan(root, [ev])["supported_files"])


    def test_encoding_prologues_stay_intact_when_canonical_placement_cannot_close(self):
        for encoding, prefix in (("latin-1", "# coding: latin-1\n"), ("utf-8-sig", "#!/usr/bin/env python3\n# coding: utf-8\n")):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "tool.py"
                raw = (prefix + "print('café')\n").encode(encoding)
                path.write_bytes(raw)
                before = evidence.read_evidence(root, path)
                _, report = examine._apply(root, [before], [], False)
                self.assertEqual(raw, path.read_bytes())
                self.assertEqual([], report["changed"])
                self.assertIn("canonical RATIOS", report["hmmm"]["tool.py"])
                self.assertEqual(0, examine._plan(root, [before])["supported_files"])
                compile(path.read_bytes(), str(path), "exec")
                # Encoding fidelity remains independently checked at the writer.
                msdmd_writer.write_text_safely(path, prefix + "print('café updated')\n", encoding, expected_raw=raw)
                compile(path.read_bytes(), str(path), "exec")
                self.assertIn("café updated", path.read_bytes().decode(encoding))

    def test_missing_hardlink_support_never_withdraws_live_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.py"
            original = b"original\n"
            path.write_bytes(original)
            with patch("pubskill_lib.msdmd_writer.os.link", side_effect=OSError("unsupported")):
                with self.assertRaises(OSError):
                    msdmd_writer.write_text_safely(path, "new\n", expected_raw=original)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual([], list(Path(tmp).glob(".examiner-originals-*")))

    def test_unrepresentable_narrative_does_not_truncate_source(self):
        class FakeProvider:
            name, model = "fake", "model-1"
            def chat(self, system, user):
                return "A snowman: \u2603"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "tool.py"
            raw = b"# coding: latin-1\nprint('caf\xe9')\n"
            path.write_bytes(raw)
            narratives, report = examine._apply(root, [evidence.read_evidence(root, path)], [FakeProvider()], True)
            self.assertEqual(raw, path.read_bytes())
            self.assertEqual({}, narratives)
            self.assertEqual([], report["changed"])
            self.assertIn("tool.py", report["hmmm"])

    def test_non_python_bom_stays_at_byte_zero(self):
        for name, body in (("main.c", "int main(void) { return 0; }\n"), ("main.rs", "fn main() {}\n")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / name
                path.write_bytes(body.encode("utf-8-sig"))
                before = evidence.read_evidence(root, path)
                examine._apply(root, [before], [], False)
                raw = path.read_bytes()
                self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
                self.assertEqual(1, raw.count(b"\xef\xbb\xbf"))
                self.assertEqual(before.sha256, evidence.read_evidence(root, path).sha256)
                examine._apply(root, [evidence.read_evidence(root, path)], [], False)
                self.assertEqual(raw, path.read_bytes())

    def test_adapterless_narratives_are_retained_without_writes(self):
        for filename, marker in (("tool.sh", "#"), ("index.php", "//")):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / filename
                original = "\n".join((f"{marker} === NARRATIVE ===", f"{marker} id: existing", f"{marker} summary: Retained explanation.", f"{marker} === END NARRATIVE ===", ""))
                path.write_text(original)
                result, report = examine._apply(root, [evidence.read_evidence(root, path)], [], False)
                self.assertEqual("Retained explanation.", result[filename]["summary"])
                self.assertEqual(original, path.read_text())
                self.assertEqual([], report["changed"])


class CanonicalMarkerTests(unittest.TestCase):
    def test_evidence_uses_vendored_msdmd_registry(self):
        markers = evidence._comment_markers()
        self.assertEqual("#", markers[".py"])
        self.assertEqual("//", markers[".ts"])
        self.assertIn(".ps1", markers)

    def test_raw_sha256_hashes_literal_python_bytes_and_honors_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "latin.py"
            raw = b"# -*- coding: latin-1 -*-\nname = 'caf\xe9'\n"
            path.write_bytes(raw)
            item = evidence.read_evidence(root, path)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item.raw_sha256)
            self.assertEqual(len(raw), item.size)
            self.assertEqual("#", item.marker)
            self.assertFalse(item.hmmm)

    def test_undecodable_non_python_source_is_hmmm_and_not_mutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "bad.js"
            raw = b"// invalid utf8: \xff\n"
            path.write_bytes(raw)
            item = evidence.read_evidence(root, path)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item.raw_sha256)
            self.assertIsNone(item.marker)
            self.assertTrue(any("encoding unresolved" in text for text in item.hmmm))


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

    def test_interpreter_non_file_modes_do_not_invent_script_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {
                    "node": "node -e console.log('ok')",
                    "python": "python -m http.server",
                    "shell": "bash -c 'echo ok'",
                }}),
                encoding="utf-8",
            )
            document = audit.audit_path(root, "pin")
            self.assertFalse([f for f in document["findings"] if f["surface"] == "deps"])

    def test_absolute_local_package_script_reports_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "node /opt/project/build.js"}}),
                encoding="utf-8",
            )
            document = audit.audit_path(root, "pin")
            claims = [f["claim"] for f in document["findings"] if f["surface"] == "deps"]
            self.assertTrue(any("escapes repository via /opt/project/build.js" in claim for claim in claims))

    def test_value_taking_interpreter_options_select_actual_file(self):
        commands = (
            "python -W ignore app.py", "python3 -X dev app.py",
            "python -uW ignore app.py", "python -Wignore app.py",
            "python --check-hash-based-pycs always app.py",
            "node --require preload.js app.py", "node -rpreload.js app.py",
            "node --import preload.js --trace-warnings app.py",
            "node --max-old-space-size 512 app.py",
            "node --watch --watch-path src app.py",
            "node --test-isolation none app.py",
            "node --experimental-test-isolation none app.py",
            "node --test-global-setup setup.js app.py",
            "node --test-rerun-failures failures.json app.py",
            "node --test-random-seed 12 app.py",
            "node --max-semi-space-size 16 app.py",
            "node --test-name-pattern 'unit|integration' app.py",
            "node --test-name-pattern 'unit;integration' app.py",
            "node --test-name-pattern '|' app.py",
            "node --test-name-pattern unit\\|integration app.py",
            "node --inspect=9229 app.py", "node --inspect app.py",
            "bash -o errexit app.py", "bash -O extglob app.py",
            "bash --rcfile startup.sh app.py", "bash -eo pipefail app.py",
            "sh +o errexit app.py", "python -- app.py",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(["app.py"], list(audit._local_script_targets(command)))
        for command in ("python -W ignore -c pass", "python -mhttp.server", "node --eval=1", "bash -ec 'echo ok'", "sh -s arg", "python - arg", "node -r preload.js -e 1", "python -W"):
            with self.subTest(command=command):
                self.assertEqual([], list(audit._local_script_targets(command)))

    def test_inspector_endpoint_requires_equals_in_node_24(self):
        # Official Node v24.15.0 attempts to load 9229 as the entry file here.
        self.assertEqual(["9229"], list(audit._local_script_targets("node --inspect 9229 app.js")))

    def test_assignment_prefixes_inspect_options_and_url_paths(self):
        commands = (
            "NODE_ENV=production node missing.js",
            "A='value with spaces' B=two node missing.js",
            "node inspect --trace-warnings missing.js",
            "node inspect --require preload.js missing.js",
            "node inspect --port=9000 --require preload.js missing.js",
        )
        for command in commands:
            self.assertEqual(["missing.js"], list(audit._local_script_targets(command)), command)
        self.assertEqual([], list(audit._local_script_targets("'A=literal-command' node missing.js")))
        for operand in ("file:missing%2Fpart.js", "file:missing%5Cpart.js", "file:missing%ZZ.js"):
            unresolved = []
            self.assertEqual([], list(audit._local_script_targets("node --entry-url " + operand, unresolved)))
            self.assertTrue(unresolved)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {"url": "node https://example.invalid/missing.js"}}))
            claims = [item["claim"] for item in audit.audit_path(root, "pin")["findings"] if item["surface"] == "deps"]
            self.assertTrue(any("missing local file https://example.invalid/missing.js" in claim for claim in claims), claims)

    def test_node_inspect_subcommand_and_malformed_urls(self):
        self.assertEqual(["missing.js"], list(audit._local_script_targets("node inspect missing.js")))
        self.assertEqual(["missing.js"], list(audit._local_script_targets("node inspect --port=9000 missing.js")))
        self.assertEqual([], list(audit._local_script_targets("node inspect localhost:9229")))
        self.assertEqual([], list(audit._local_script_targets("node inspect -p 1234")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inspect").mkdir()
            (root / "package.json").write_text(json.dumps({"scripts": {
                "inspect": "node inspect missing.js",
                "nul": "node --entry-url file:///tmp/%00.js",
                "raw-nul": "node bad\u0000name.js",
            }}))
            document = audit.audit_path(root, "pin")
            self.assertTrue(any("missing local file missing.js" in f["claim"] for f in document["findings"]))
            self.assertEqual(2, sum("NUL-containing" in item for item in document["hmmm"]))

    def test_quoted_segments_and_entrypoint_urls(self):
        self.assertEqual(["first.js", "second.js"], list(audit._local_script_targets("node --test-name-pattern 'a|b' first.js && node second.js")))
        self.assertEqual([], list(audit._local_script_targets("node --entry-url 'data:text/javascript,console.log(1);'")))
        self.assertEqual(["/definitely/missing file.js"], list(audit._local_script_targets("node --entry-url file:///definitely/missing%20file.js")))
        self.assertEqual(["./local file.js"], list(audit._local_script_targets("node --entry-url './local%20file.js?debug=1#part'")))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({"scripts": {
                "file": "node --entry-url file:///definitely/missing.js",
                "data": "node --entry-url 'data:text/javascript,console.log(1);'",
                "quoted": "node --test-name-pattern 'unit|integration' missing.js",
            }}))
            claims = [f["claim"] for f in audit.audit_path(root, "pin")["findings"] if f["surface"] == "deps"]
            self.assertEqual(2, len(claims))
            self.assertTrue(any("escapes repository via /definitely/missing.js" in claim for claim in claims))
            self.assertTrue(any("missing local file missing.js" in claim for claim in claims))

    def test_word_expansions_preserve_independent_literal_entrypoints(self):
        for command, expected in (
            ('node missing.js "$ARG"', ["missing.js"]),
            ('python missing.py "$ARG"', ["missing.py"]),
            ('node -- missing.js "$ARG"', ["missing.js"]),
            ('node build~backup.js', ["build~backup.js"]),
            ('node $SCRIPT && node missing.js', ["missing.js"]),
            ('node *.js && node missing.js', ["missing.js"]),
            ('node "$SCRIPT" && node missing.js', ["missing.js"]),
            ('node missing.js "$(pwd)"', ["missing.js"]),
            ('node ~/script.js', []),
            ('node -- $SCRIPT', []),
            ('node $(cd ..; node hidden.js; pwd) && node uncertain.js', []),
        ):
            with self.subTest(command=command):
                gaps = []
                self.assertEqual(list(audit._local_script_targets(command, gaps)), expected)
                if "$" in command or "*" in command or "~/" in command:
                    self.assertTrue(gaps)

    def test_exit_comments_paths_and_unresolved_shell_context(self):
        for command in ("python --help missing.py", "python -uV missing.py", "node --version missing.js", "bash --help missing.sh"):
            self.assertEqual([], list(audit._local_script_targets(command)), command)
        self.assertEqual(["real.js"], list(audit._local_script_targets("node real.js # disabled && node missing.js")))
        self.assertEqual(["real.js", "next.js"], list(audit._local_script_targets("node real.js # disabled && node missing.js\nnode next.js")))
        self.assertEqual(["missing.js"], list(audit._local_script_targets("/usr/bin/node missing.js")))
        self.assertEqual(["missing.py"], list(audit._local_script_targets("./venv/bin/python missing.py")))
        self.assertEqual(["$literal.js"], list(audit._local_script_targets("node '$literal.js'")))
        for command in ("node 'missing.js", "cd frontend && node build.js", "node --unknown-option value missing.js", "unknown-runner missing.js", "node $SCRIPT", "node *.js", "(cd frontend && node build.js)", "node < input.js", "node \\\n missing.js"):
            unresolved = []
            self.assertEqual([], list(audit._local_script_targets(command, unresolved)), command)
            self.assertTrue(unresolved, command)

    def test_non_object_package_manifest_is_target_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("[]\n", encoding="utf-8")
            document = audit.audit_path(root, "pin")
            claims = [f["claim"] for f in document["findings"] if f["surface"] == "deps"]
            self.assertIn("package.json top level is not an object", claims)


if __name__ == "__main__":
    unittest.main()
