"""Reject wrong-version mirrors and tampered checkpoints before model loading."""

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_model_access.py"
SPEC = importlib.util.spec_from_file_location("model_access", SCRIPT)
access = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(access)


class ModelIdentityTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "version_id": 123, "filename": "expected.safetensors", "size_bytes": 4,
            "sha256": hashlib.sha256(b"good").hexdigest(),
            "mirror": {"filename": "expected.safetensors"},
        }

    def test_wrong_publisher_version_is_rejected(self):
        with self.assertRaises(ValueError):
            access.publisher_file({"id": 140737, "modelVersions": [{"id": 999, "files": []}]}, self.model)

    def test_similar_filename_does_not_establish_identity(self):
        with self.assertRaises(ValueError):
            access.mirror_file([{"path": "expected-v2.safetensors", "size": 4}], self.model)

    def test_mirror_checksum_must_match_publisher(self):
        with self.assertRaises(ValueError):
            access.mirror_file([{"path": "expected.safetensors", "size": 4, "lfs": {"oid": "0" * 64}}], self.model)

    def test_same_size_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint"
            path.write_bytes(b"evil")
            with self.assertRaises(ValueError):
                access.verify_local(path, self.model)
            path.write_bytes(b"good")
            self.assertTrue(access.verify_local(path, self.model)["verified"])


if __name__ == "__main__":
    unittest.main()
