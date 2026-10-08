# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "pillow>=11,<13", "plyfile>=1,<2", "pyarrow>=19,<24", "opencv-python-headless>=4.11,<5"]
# ///
"""Standalone prep contract tests: uv run tools/test_scannet_prep.py."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scannet_prep as prep


def synthetic(path: Path, *, corrupt=False, missing=False, unsafe=False):
    mesh = b"ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n1 0 0\n0 1 0\n"
    segments = io.BytesIO()
    np.save(segments, np.array([1, 1, 2], dtype=np.int32))
    files = {"mesh/vh_clean_2.ply": mesh, "mesh/superpoints.npy": segments.getvalue(),
             "calib/intrinsics.json": b"{}", "frames/index.parquet": b"index",
             "frames/color/000000.jpg": b"color", "frames/depth/000000.png": b"depth",
             "frames/pose/000000.txt": b"pose"}
    manifest = {"format_version": "s3dpkg/1", "status": "complete", "scan_id": "scene0000_00",
                "aligned": False, "axis_alignment": np.eye(4).tolist(),
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    if corrupt:
        files["frames/color/000000.jpg"] = b"wrong"
    if missing:
        files.pop("frames/depth/000000.png")
    if unsafe:
        files["C:/escape.txt"] = b"unsafe"
    files["manifest.json"] = json.dumps(manifest).encode()
    with tarfile.open(path, "w:") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


class ContractTests(unittest.TestCase):
    def test_valid_and_corrupt_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.s3dpkg"
            synthetic(path)
            self.assertFalse(prep.verify(path)["aligned"])
            synthetic(path, corrupt=True)
            with self.assertRaisesRegex(prep.PackageError, "checksum"):
                prep.verify(path)
            result = subprocess.run([sys.executable, prep.__file__, "verify", str(path)],
                                    capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checksum", result.stderr)
            synthetic(path, missing=True)
            with self.assertRaisesRegex(prep.PackageError, "members"):
                prep.verify(path)

    def test_windows_drive_member_is_unsafe_on_every_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.s3dpkg"
            synthetic(path, unsafe=True)
            with self.assertRaisesRegex(prep.PackageError, "unsafe"):
                prep.verify(path)


if __name__ == "__main__":
    unittest.main()
