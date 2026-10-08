"""The import-side implementation of the s3dpkg/1 wire contract."""

import hashlib
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

import numpy as np
from plyfile import PlyData

SCAN_ID = re.compile(r"scene\d{4}_\d{2}$")
REQUIRED = {"mesh/vh_clean_2.ply", "mesh/superpoints.npy", "calib/intrinsics.json",
            "frames/index.parquet"}


class InvalidPackage(ValueError):
    """A Package violates the published s3dpkg/1 contract."""


def verify_package(path: Path) -> dict:
    if path.suffix != ".s3dpkg":
        raise InvalidPackage("The file must end in .s3dpkg")
    try:
        with tarfile.open(path, "r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise InvalidPackage("Duplicate archive member")
            for member in members:
                name = PurePosixPath(member.name)
                if (not member.isfile() or name.is_absolute() or ".." in name.parts
                        or "\\" in member.name or ":" in member.name):
                    raise InvalidPackage(f"Unsafe archive member: {member.name}")
            if "manifest.json" not in names:
                raise InvalidPackage("Missing manifest.json")
            manifest = json.load(archive.extractfile("manifest.json"))
            if manifest.get("format_version") != "s3dpkg/1":
                raise InvalidPackage("Unsupported format_version")
            if manifest.get("status") != "complete":
                raise InvalidPackage("Package status is not complete")
            if not SCAN_ID.fullmatch(manifest.get("scan_id", "")):
                raise InvalidPackage("Invalid scan_id")
            alignment = np.asarray(manifest.get("axis_alignment"), dtype=np.float64)
            if (alignment.shape != (4, 4) or not np.isfinite(alignment).all()
                    or not isinstance(manifest.get("aligned"), bool)):
                raise InvalidPackage("Invalid axis alignment matrix or aligned flag")
            if not manifest["aligned"] and not np.allclose(alignment, np.eye(4)):
                raise InvalidPackage("Unaligned Package must use identity alignment")
            files = manifest.get("files")
            if not isinstance(files, dict) or set(names) != set(files) | {"manifest.json"}:
                raise InvalidPackage("Manifest file list does not match archive members")
            if not REQUIRED.issubset(files):
                raise InvalidPackage("Missing required member")
            frame_ids = {name.split("/")[2].split(".")[0] for name in files
                         if name.startswith("frames/color/")}
            if not frame_ids or any(f"frames/{folder}/{fid}.{extension}" not in files
                                    for fid in frame_ids for folder, extension
                                    in (("depth", "png"), ("pose", "txt"))):
                raise InvalidPackage("Keyframe is missing color, depth, or pose")
            for member in members:
                if member.name == "manifest.json":
                    continue
                digest = hashlib.sha256()
                source = archive.extractfile(member)
                while block := source.read(1024 * 1024):
                    digest.update(block)
                if digest.hexdigest() != files[member.name]:
                    raise InvalidPackage(f"SHA-256 mismatch: {member.name}")
            mesh = PlyData.read(io.BytesIO(archive.extractfile("mesh/vh_clean_2.ply").read()))
            segments = np.load(io.BytesIO(archive.extractfile("mesh/superpoints.npy").read()),
                               allow_pickle=False)
            if segments.dtype != np.int32 or segments.ndim != 1 or len(segments) != len(mesh["vertex"]):
                raise InvalidPackage("Superpoint dtype or vertex count mismatch")
            return manifest
    except (tarfile.TarError, OSError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, InvalidPackage):
            raise
        raise InvalidPackage(f"Unreadable Package: {exc}") from exc
