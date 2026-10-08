# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "pillow>=11,<13", "plyfile>=1,<2", "pyarrow>=19,<24", "opencv-python-headless>=4.11,<5"]
# ///
"""Standalone prep contract tests: uv run tools/test_scannet_prep.py."""

import hashlib
import io
import json
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np
import scannet_prep as prep
from PIL import Image
from plyfile import PlyData


def raw_scan(root: Path) -> Path:
    scan = root / "scene0000_00"
    scan.mkdir()
    (scan / "scene0000_00_vh_clean_2.ply").write_text(
        "ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\n"
        "property float nx\nproperty float ny\nproperty float nz\nelement face 1\n"
        "property list uchar int vertex_indices\nend_header\n"
        "0 0 0 1 0 0\n1 0 0 1 0 0\n0 1 0 1 0 0\n3 0 1 2\n")
    (scan / "scene0000_00_vh_clean_2.0.010000.segs.json").write_text('{"segIndices":[7,7,8]}')
    (scan / "scene0000_00.txt").write_text("axisAlignment = 0 -1 0 10 1 0 0 20 0 0 1 0 0 0 0 1\n")
    jpeg = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(jpeg, format="JPEG")
    color = jpeg.getvalue()
    depth = zlib.compress(np.full((2, 2), 1000, dtype="<u2").tobytes())
    pose = np.eye(4, dtype=np.float32)
    pose[:3, 3] = [1, 0, 2]
    identity = struct.pack("<16f", *np.eye(4).flatten())
    header = struct.pack("<IQ", 4, 0) + identity * 4 + struct.pack("<iiIIIIfQ", 2, 1, 2, 2, 2, 2, 1000, 1)
    frame = struct.pack("<16fQQQQ", *pose.flatten(), 0, 0, len(color), len(depth)) + color + depth
    (scan / "scene0000_00.sens").write_bytes(header + frame)
    return scan


def synthetic(path: Path, *, corrupt=False, missing=False, unsafe=False, version="s3dpkg/2"):
    mesh = b"ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n1 0 0\n0 1 0\n"
    segments = io.BytesIO()
    np.save(segments, np.array([1, 1, 2], dtype=np.int32))
    files = {"mesh/vh_clean_2.ply": mesh, "mesh/superpoints.npy": segments.getvalue(),
             "calib/intrinsics.json": b"{}", "frames/index.parquet": b"index",
             "frames/color/000000.jpg": b"color", "frames/depth/000000.png": b"depth",
             "frames/pose/000000.txt": b"pose"}
    manifest = {"format_version": version, "status": "complete", "scan_id": "scene0000_00",
                "coordinate_frame": "axis_aligned", "source_axis_alignment": np.eye(4).tolist(),
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
    def test_pack_applies_alignment_to_mesh_normals_and_pose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan = raw_scan(root)
            package = prep.pack(scan, root / "preprocessing")
            manifest = prep.verify(package)
            self.assertEqual(manifest["format_version"], "s3dpkg/2")
            self.assertEqual(manifest["coordinate_frame"], "axis_aligned")
            with tarfile.open(package) as archive:
                mesh = PlyData.read(io.BytesIO(archive.extractfile("mesh/vh_clean_2.ply").read()))
                vertices = mesh["vertex"].data
                self.assertEqual(vertices["x"].tolist(), [10, 10, 9])
                self.assertEqual(vertices["y"].tolist(), [20, 21, 20])
                self.assertEqual(vertices["nx"].tolist(), [0, 0, 0])
                self.assertEqual(vertices["ny"].tolist(), [1, 1, 1])
                pose = np.loadtxt(io.BytesIO(archive.extractfile("frames/pose/000000.txt").read()))
                self.assertEqual(pose[:3, 3].tolist(), [10, 21, 2])
                self.assertEqual(mesh["face"].data["vertex_indices"][0].tolist(), [0, 1, 2])
                superpoints = np.load(io.BytesIO(archive.extractfile("mesh/superpoints.npy").read()))
                self.assertEqual(superpoints.tolist(), [7, 7, 8])

    def test_valid_and_corrupt_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.s3dpkg"
            synthetic(path)
            self.assertEqual(prep.verify(path)["coordinate_frame"], "axis_aligned")
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

    def test_old_packages_require_preprocessing_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.s3dpkg"
            synthetic(path, version="s3dpkg/1")
            with self.assertRaisesRegex(prep.PackageError, "rerun preprocessing"):
                prep.verify(path)

    def test_missing_or_invalid_alignment_produces_no_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan = raw_scan(root)
            metadata = scan / "scene0000_00.txt"
            metadata.unlink()
            with self.assertRaisesRegex(prep.PackageError, "alignment: missing"):
                prep.pack(scan, root / "preprocessing")
            for matrix in ("nan " * 16, "bad", "2 0 0 0 0 2 0 0 0 0 2 0 0 0 0 1"):
                metadata.write_text("axisAlignment = " + matrix)
                with self.assertRaisesRegex(prep.PackageError, "alignment:"):
                    prep.pack(scan, root / "preprocessing")
            self.assertFalse(list((root / "preprocessing").glob("*.s3dpkg")))
            metadata.write_text("axisAlignment = 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1")
            package = prep.pack(scan, root / "preprocessing")
            self.assertEqual(prep.verify(package)["source_axis_alignment"], np.eye(4).tolist())


if __name__ == "__main__":
    unittest.main()
