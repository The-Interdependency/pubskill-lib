"""Usage: python -m unittest discover -s tests. Reject an unqualified compressor."""
import unittest
from unittest.mock import patch
from tools.build_release import check_compressor


class CompressorTest(unittest.TestCase):
    def test_compressor_identity_is_enforced(self):
        with patch("tools.build_release.zlib.ZLIB_VERSION", "1.3.1"), patch("tools.build_release.zlib.ZLIB_RUNTIME_VERSION", "1.3.1"):
            self.assertEqual(check_compressor()["runtime_version"], "1.3.1")
        for compile_version, runtime_version in (("1.3", "1.3.1"), ("1.3.1", "1.3")):
            with patch("tools.build_release.zlib.ZLIB_VERSION", compile_version), patch("tools.build_release.zlib.ZLIB_RUNTIME_VERSION", runtime_version):
                with self.assertRaisesRegex(RuntimeError, "require zlib"):
                    check_compressor()
