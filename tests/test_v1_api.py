"""Phase B application-layer tests: identity, catalog, collection, query,
acquisition boundaries, and the transport-neutral v1 API.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pubskill_lib import api, collections, identity, queries
from pubskill_lib.acquisition import AcquisitionError, acquire_repository, valid_repo_url

REPO = Path(__file__).resolve().parents[1]


class IdentityTests(unittest.TestCase):
    def test_envelope_carries_producer_consumer_and_catalog(self):
        envelope = api.v1_identity()
        self.assertEqual(envelope["schema"], "pubskill-lib.api")
        self.assertEqual(envelope["version"], 1)
        self.assertEqual(envelope["route"], "identity")
        ident = envelope["identity"]
        self.assertEqual(ident["producer"]["repository"], "The-Interdependency/skill-lib")
        self.assertRegex(ident["producer"]["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(ident["consumer"]["repository"], "The-Interdependency/pubskill-lib")
        self.assertRegex(ident["catalog"]["catalog_digest"], r"^[0-9a-f]{64}$")

    def test_runtime_status_reports_declared_runtimes(self):
        status = collections.runtime_status()
        self.assertEqual(set(status["python_runtimes"]), {
            "yaml", "docstring_parser", "tree_sitter", "tree_sitter_rust",
            "tree_sitter_java", "tree_sitter_c", "tree_sitter_cpp",
        })
        self.assertEqual(
            status["missing"],
            [name for name, present in status["python_runtimes"].items() if not present],
        )


class CatalogTests(unittest.TestCase):
    def test_list_skills_is_full_catalog_bound_to_pin(self):
        response = api.v1_list_skills()
        self.assertEqual(response["skill_count"], 44)
        pin = identity.producer_identity()["commit"]
        for skill in response["skills"]:
            self.assertEqual(skill["source_commit"], pin)
            self.assertRegex(skill["digest"], r"^[0-9a-f]{64}$")

    def test_get_skill_and_resource(self):
        skill = api.v1_get_skill("msdmd")["skill"]
        self.assertEqual(skill["name"], "msdmd")
        self.assertIn("Load this when", skill["skill_md"])
        resource_paths = {item["path"] for item in skill["resources"]}
        self.assertIn("parsers/universal.py", resource_paths)
        resource = api.v1_get_resource("msdmd", "parsers/universal.py")["resource"]
        self.assertIn("parse_text", resource["content_utf8"])

    def test_resource_retrieval_rejects_escape_and_missing(self):
        with self.assertRaises(ValueError):
            api.v1_get_resource("msdmd", "../skills.json")
        with self.assertRaises(ValueError):
            api.v1_get_resource("msdmd", "/etc/passwd")
        with self.assertRaises(ValueError):
            api.v1_get_resource("msdmd", "not-a-file.txt")
        with self.assertRaises(ValueError):
            api.v1_get_skill("not-a-skill")

    def test_resource_retrieval_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / "skills"
            skill_dir = skills / "sym-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: sym-skill\ndescription: test\n---\n", encoding="utf-8")
            (skill_dir / "real.txt").write_text("real", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (skill_dir / "link.txt").symlink_to(outside)
            catalog_manifest = {
                "schema": "pubskill-lib.catalog",
                "version": 1,
                "producer": {"repository": "The-Interdependency/skill-lib", "commit": "0" * 40},
                "skill_count": 1,
                "propagated_set_digest": "0" * 64,
                "skills": [{
                    "name": "sym-skill",
                    "path": "sym-skill/SKILL.md",
                    "digest": "0" * 64,
                    "source_commit": "0" * 40,
                }],
            }
            (skills / "catalog.json").write_text(json.dumps(catalog_manifest), encoding="utf-8")
            with mock.patch.dict(os.environ, {"PUBSKILL_SKILLS_ROOT": str(skills)}):
                self.assertEqual(
                    api.v1_get_resource("sym-skill", "real.txt")["resource"]["content_utf8"],
                    "real",
                )
                with self.assertRaises(ValueError):
                    api.v1_get_resource("sym-skill", "link.txt")

    def test_resolve_returns_scored_candidates_not_authority(self):
        resolved = api.v1_resolve("metadata collection")
        self.assertEqual(resolved["method"], "keyword-overlap-v1")
        self.assertFalse(resolved["authoritative"])
        self.assertTrue(resolved["candidates"])
        self.assertIn("msdmd", [item["name"] for item in resolved["candidates"]])
        with self.assertRaises(ValueError):
            api.v1_resolve("")


def _make_git_fixture(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "fixture"], check=True)
    (root / "example.py").write_text(
        "def double(value: int) -> int:\n"
        '    """Return twice the supplied value."""\n'
        "    return value * 2\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)


class CollectionTests(unittest.TestCase):
    def test_collect_metadata_emits_valid_schema2_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            _make_git_fixture(root)
            result = collections.collect_metadata(root, "fixture/repo", strict=True)
            self.assertEqual(result.collection["schema"], "the-interdependency.msdmd-collection")
            self.assertEqual(result.collection["schema_version"], "2.0.0")
            self.assertEqual(result.collection["repo"], "fixture/repo")
            self.assertTrue(result.collection["facts"])
            self.assertEqual(result.returncode, 0)

    def test_collection_never_executes_target_code(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            root.mkdir()
            sentinel = base / "executed"
            (root / "example.py").write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "fixture"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
            collections.collect_metadata(root, "fixture/exec", strict=True)
            self.assertFalse(sentinel.exists(), "collector executed inspected application code")

    def test_strict_collection_fails_on_required_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            _make_git_fixture(root)
            with self.assertRaises(collections.CollectionError):
                collections.collect_metadata(
                    root,
                    "fixture/repo",
                    strict=True,
                    require_sources=("does-not-exist.json",),
                )


class QueryTests(unittest.TestCase):
    def test_query_filters_by_convention_and_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            _make_git_fixture(root)
            collection = collections.collect_metadata(root, "fixture/repo", strict=True).collection
            result = queries.query_collection(collection, convention="python.source-metadata")
            self.assertGreater(result["counts"]["matched_facts"], 0)
            for fact in result["matched_facts"]:
                self.assertIn("python.source-metadata", fact["convention"].values())
            empty = queries.query_collection(collection, convention="not-a-convention")
            self.assertEqual(empty["counts"]["matched_facts"], 0)

    def test_v1_query_rejects_non_collection(self):
        with self.assertRaises(ValueError):
            api.v1_query(collection={"schema": "not-msdmd"})


class AcquisitionBoundaryTests(unittest.TestCase):
    def test_url_validation(self):
        self.assertTrue(valid_repo_url("https://github.com/owner/repo"))
        self.assertTrue(valid_repo_url("https://gitlab.com/owner/repo/sub"))
        for bad in (
            "http://github.com/owner/repo",
            "https://github.com/owner/repo.git?x=1",
            "https://github.com/owner/repo#frag",
            "https://user@github.com/owner/repo",
            "https://github.com:8443/owner/repo",
            "ssh://git@github.com/owner/repo",
            "file:///tmp/repo",
            "https://github.com/owner",
            "https://github.com/owner/repo/too/many",
            "https://github.com/owner/../repo",
        ):
            self.assertFalse(valid_repo_url(bad), bad)

    def test_acquire_rejects_bad_url(self):
        with self.assertRaises(AcquisitionError):
            with acquire_repository("https://github.com/owner/../repo"):
                pass


class ServiceBoundaryTests(unittest.TestCase):
    def test_unknown_request_fields_are_rejected(self):
        import service
        with self.assertRaises(ValueError):
            service._reject_unknown_fields({"repo_url": "x", "extra": 1}, {"repo_url"}, "inspect")


if __name__ == "__main__":
    unittest.main()
