"""Phase C MCP transport tests: JSON-RPC handling, tool schemas, tool calls,
HTTP bytes handling, self-test, and the replayable metadata fixture.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from pubskill_lib import api, mcp_server

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".agents" / "skills"


def rpc(request_id, method, params=None):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


class McpJsonRpcTests(unittest.TestCase):
    def test_initialize_negotiates_protocol_and_capabilities(self):
        response = mcp_server.handle_jsonrpc(
            rpc(1, "initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            })
        )
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(response["result"]["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "pubskill-lib")

    def test_notification_returns_none(self):
        self.assertIsNone(
            mcp_server.handle_jsonrpc(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
            )
        )

    def test_tools_list_exposes_all_pubskill_tools(self):
        response = mcp_server.handle_jsonrpc(rpc(2, "tools/list"))
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertEqual(names, {
            "pubskill_identity",
            "pubskill_list_skills",
            "pubskill_get_skill",
            "pubskill_get_resource",
            "pubskill_collect_metadata",
            "pubskill_query_metadata",
            "pubskill_resolve_skills",
        })
        for tool in response["result"]["tools"]:
            self.assertIn("inputSchema", tool)
            self.assertIn("description", tool)

    def test_tools_call_identity_and_catalog(self):
        response = mcp_server.handle_jsonrpc(
            rpc(3, "tools/call", {"name": "pubskill_identity", "arguments": {}})
        )
        self.assertFalse(response["result"]["isError"])
        text = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(text["schema"], "pubskill-lib.api")

        response = mcp_server.handle_jsonrpc(
            rpc(4, "tools/call", {"name": "pubskill_list_skills", "arguments": {}})
        )
        text = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(text["skill_count"], 44)

    def test_tools_call_get_skill_and_resource(self):
        response = mcp_server.handle_jsonrpc(
            rpc(5, "tools/call", {"name": "pubskill_get_skill", "arguments": {"name": "msdmd"}})
        )
        text = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(text["skill"]["name"], "msdmd")

        response = mcp_server.handle_jsonrpc(
            rpc(6, "tools/call", {
                "name": "pubskill_get_resource",
                "arguments": {"name": "msdmd", "path": "parsers/universal.py"},
            })
        )
        text = json.loads(response["result"]["content"][0]["text"])
        self.assertIn("parse_text", text["resource"]["content_utf8"])

    def test_tools_call_resolve_returns_candidates(self):
        response = mcp_server.handle_jsonrpc(
            rpc(7, "tools/call", {
                "name": "pubskill_resolve_skills",
                "arguments": {"query": "metadata collection"},
            })
        )
        text = json.loads(response["result"]["content"][0]["text"])
        self.assertFalse(text["authoritative"])
        self.assertIn("msdmd", [item["name"] for item in text["candidates"]])

    def test_tools_call_collect_rejects_disallowed_host(self):
        response = mcp_server.handle_jsonrpc(
            rpc(8, "tools/call", {
                "name": "pubskill_collect_metadata",
                "arguments": {"repo_url": "https://example.com/owner/repo"},
            })
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("supported public HTTPS Git repository required", response["result"]["content"][0]["text"])

    def test_tools_call_unknown_tool_returns_error_result(self):
        response = mcp_server.handle_jsonrpc(
            rpc(9, "tools/call", {"name": "not-a-tool", "arguments": {}})
        )
        self.assertTrue(response["result"]["isError"])

    def test_method_not_found_returns_jsonrpc_error(self):
        response = mcp_server.handle_jsonrpc(rpc(10, "no/such/method"))
        self.assertEqual(response["error"]["code"], -32601)


class McpHttpBytesTests(unittest.TestCase):
    def test_accept_header_is_enforced(self):
        status, _, _ = mcp_server.handle_http_bytes(b"{}", "text/html")
        self.assertEqual(status, 406)

    def test_parse_error_returns_400(self):
        status, content_type, data = mcp_server.handle_http_bytes(
            b"not-json", "application/json, text/event-stream"
        )
        self.assertEqual(status, 400)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(data)["error"]["code"], -32700)

    def test_initialize_over_http_bytes(self):
        payload = json.dumps(rpc(1, "initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        })).encode()
        status, content_type, data = mcp_server.handle_http_bytes(
            payload, "application/json, text/event-stream"
        )
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(data)["result"]["protocolVersion"], "2025-11-25")

    def test_batch_requests_are_supported(self):
        payload = json.dumps([
            rpc(1, "tools/list"),
            rpc(2, "ping"),
        ]).encode()
        status, _, data = mcp_server.handle_http_bytes(
            payload, "application/json, text/event-stream"
        )
        self.assertEqual(status, 200)
        responses = json.loads(data)
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["result"]["tools"][0]["name"], "pubskill_identity")


class McpSelfTestTests(unittest.TestCase):
    def test_self_test_passes(self):
        result = subprocess.run(
            [sys.executable, "-m", "pubskill_lib.mcp_server", "--self-test"],
            cwd=REPO,
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: initialize negotiates 2025-11-25", result.stdout)


class FixtureReplayTests(unittest.TestCase):
    def _expected_collection(self) -> Path:
        version_tag = f"py{sys.version_info[0]}{sys.version_info[1]}"
        return REPO / "examples" / "metadata-repo-expected" / f"collection-{version_tag}.json"

    def test_fixture_collection_replays_byte_for_byte(self):
        expected = self._expected_collection()
        if not expected.is_file():
            self.skipTest(f"no expected fixture collection for {sys.version_info[:2]}")
        env = dict(os.environ)
        pythonpath = str(SKILLS)
        if env.get("PYTHONPATH"):
            pythonpath += os.pathsep + env["PYTHONPATH"]
        env["PYTHONPATH"] = pythonpath
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "msdmd.collect",
                "--root",
                str(REPO / "examples" / "metadata-repo"),
                "--repo",
                "fixture/metadata-repo",
                "--snapshot-identity",
                "--strict",
                "--json",
                "--out",
                str(expected),
                "--check",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fixture_collection_has_schema2_facts_and_declarations(self):
        expected = self._expected_collection()
        if not expected.is_file():
            self.skipTest(f"no expected fixture collection for {sys.version_info[:2]}")
        collection = json.loads(expected.read_text(encoding="utf-8"))
        self.assertEqual(collection["schema"], "the-interdependency.msdmd-collection")
        self.assertEqual(collection["schema_version"], "2.0.0")
        self.assertEqual(collection["source"]["revision_kind"], "content-snapshot")
        self.assertGreater(len(collection["facts"]), 0)
        self.assertGreater(len(collection["declarations"]), 0)
        self.assertTrue(
            all(item.get("severity") != "error" for item in collection["diagnostics"]),
            "fixture collection contains error diagnostics",
        )


if __name__ == "__main__":
    unittest.main()
