"""Public Git acquisition must not borrow the host's authentication."""
from __future__ import annotations

import functools
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from unittest import mock

from pubskill_lib import acquisition


class GitCredentialBoundaryTests(unittest.TestCase):
    def test_all_acquisition_commands_receive_only_the_isolated_environment(self):
        inherited = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": "/host/home",
            "XDG_CONFIG_HOME": "/host/config",
            "GIT_ASKPASS": "/host/askpass",
            "SSH_ASKPASS": "/host/ssh-askpass",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": "Authorization: Bearer test-secret",
            "GIT_CONFIG_PARAMETERS": "'http.extraHeader=Authorization: Bearer test-secret'",
            "GIT_CONFIG_SYSTEM": "/host/system-config",
            "GIT_CONFIG_GLOBAL": "/host/global-config",
            "GIT_DIR": "/host/private-repo/.git",
            "GIT_WORK_TREE": "/host/private-repo",
            "GIT_EXEC_PATH": "/host/git-programs",
            "GIT_TEMPLATE_DIR": "/host/git-templates",
            "HTTPS_PROXY": "https://user:password@proxy.invalid",
            "LD_PRELOAD": "/host/loader.so",
            "OTHER_SECRET": "must-not-travel",
        }
        environments = []

        def git(*args, **kwargs):
            env = kwargs["env"]
            environments.append(env)
            self.assertNotEqual(env["HOME"], inherited["HOME"])
            self.assertTrue(Path(env["HOME"]).is_dir())
            self.assertEqual(list(Path(env["HOME"]).iterdir()), [])
            return subprocess.CompletedProcess(args[0], 0, "a" * 40, "")

        with mock.patch.dict(os.environ, inherited, clear=True), \
                mock.patch.object(acquisition.subprocess, "run", side_effect=git), \
                mock.patch.object(acquisition, "_run_git_limited", side_effect=git):
            with acquisition.acquire_repository("https://github.com/owner/repo") as result:
                self.assertEqual(result.resolved_commit, "a" * 40)
        self.assertEqual(len(environments), 5)
        for env in environments:
            expected = {"PATH", "HOME", "XDG_CONFIG_HOME", *acquisition._GIT_ISOLATED_ENV}
            if os.name == "nt":
                expected.update({"SYSTEMROOT", "USERPROFILE"})
            self.assertEqual(set(env), expected)
            self.assertEqual(env["PATH"], inherited["PATH"])
            self.assertEqual(env["XDG_CONFIG_HOME"], env["HOME"])
            self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(env["GIT_CONFIG_SYSTEM"], os.devnull)
            self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertFalse(Path(environments[0]["HOME"]).exists())

    def test_isolated_git_still_reads_a_public_repository(self):
        class PublicRepository(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            env = acquisition._git_environment(home)
            repository = root / "public.git"

            def git(*args, input=None):
                return subprocess.run(
                    ["git", *acquisition._GIT_SAFE_CONFIG, *args],
                    env=env, input=input, check=True, capture_output=True,
                    text=True, timeout=10,
                ).stdout.strip()

            git("init", "--bare", str(repository))
            tree = git("-C", str(repository), "mktree", input="")
            commit = git(
                "-C", str(repository), "-c", "user.name=Test Fixture",
                "-c", "user.email=fixture@example.invalid", "commit-tree", tree,
                input="Public fixture\n",
            )
            git("-C", str(repository), "update-ref", "refs/heads/main", commit)
            git("-C", str(repository), "update-server-info")
            server = HTTPServer(
                ("127.0.0.1", 0), functools.partial(PublicRepository, directory=str(root)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                refs = git("ls-remote", f"http://127.0.0.1:{server.server_port}/public.git")
                self.assertIn(f"{commit}\trefs/heads/main", refs)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_real_git_cannot_authenticate_with_inherited_credentials(self):
        headers = []

        class Challenge(BaseHTTPRequestHandler):
            def do_GET(self):
                headers.append(self.headers.get("Authorization"))
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="test-only"')
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Challenge)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                host_home, clean_home = root / "host", root / "isolated"
                host_home.mkdir()
                clean_home.mkdir()
                marker = root / "askpass-ran"
                askpass = root / "askpass"
                askpass.write_text(
                    f"#!/bin/sh\nprintf invoked > '{marker}'\nprintf test-only-credential\\n\n",
                    encoding="utf-8",
                )
                askpass.chmod(0o700)
                (host_home / ".netrc").write_text(
                    "machine 127.0.0.1 login test-only-user password test-only-password\n",
                    encoding="utf-8",
                )
                (host_home / ".netrc").chmod(0o600)
                cases = {
                    "askpass": {"GIT_ASKPASS": str(askpass)},
                    "ssh_askpass": {"SSH_ASKPASS": str(askpass)},
                    "config_pairs": {
                        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraHeader",
                        "GIT_CONFIG_VALUE_0": "Authorization: Bearer test-only-token",
                    },
                    "config_parameters": {
                        "GIT_CONFIG_PARAMETERS": "'http.extraHeader=Authorization: Bearer test-only-token'",
                    },
                    "netrc": {"HOME": str(host_home)},
                }
                url = f"http://127.0.0.1:{server.server_port}/private.git"
                command = ["git", *acquisition._GIT_SAFE_CONFIG, "ls-remote", url]
                for name, credentials in cases.items():
                    with self.subTest(channel=name):
                        inherited = {
                            "PATH": os.environ.get("PATH", os.defpath),
                            "HOME": str(clean_home), "XDG_CONFIG_HOME": str(clean_home),
                            **acquisition._GIT_ISOLATED_ENV, **credentials,
                        }
                        # Establish that this fixture detects the old inherited
                        # environment behavior, using dummy localhost secrets.
                        headers.clear()
                        unsafe = subprocess.run(command, env=inherited, capture_output=True, timeout=10)
                        self.assertNotEqual(unsafe.returncode, 0)
                        self.assertTrue(any(headers), (name, unsafe.stderr))
                        if marker.exists():
                            marker.unlink()
                        headers.clear()
                        with mock.patch.dict(os.environ, inherited, clear=True):
                            isolated = acquisition._git_environment(clean_home)
                        result = subprocess.run(command, env=isolated, capture_output=True, timeout=10)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertTrue(headers, result.stderr)
                        self.assertFalse(any(headers), (name, headers))
                        self.assertFalse(marker.exists(), name)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
