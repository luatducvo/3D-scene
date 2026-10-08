# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "pillow>=11,<13", "plyfile>=1,<2", "pyarrow>=19,<24", "opencv-python-headless>=4.11,<5"]
# ///
"""Build and verify aligned s3dpkg/2 Packages outside the S3D application."""

import argparse
import csv
import hashlib
import io
import json
import re
import struct
import tarfile
import tempfile
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
from plyfile import PlyData

VERSION = "0.2.0"
SCAN_RE = re.compile(r"scene\d{4}_\d{2}$")


class PackageError(Exception):
    """An invalid source scan or Package with a named failing step."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_exact(stream, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise PackageError("sens: truncated stream")
    return data


def unpack(stream, code: str):
    return struct.unpack("<" + code, read_exact(stream, struct.calcsize("<" + code)))


def sens_header(stream) -> dict:
    version = unpack(stream, "I")[0]
    if version != 4:
        raise PackageError(f"sens: unsupported version {version}")
    name_length = unpack(stream, "Q")[0]
    if name_length > 4096:
        raise PackageError("sens: invalid sensor name length")
    read_exact(stream, name_length)
    matrices = [np.array(unpack(stream, "16f"), dtype=np.float64).reshape(4, 4)
                for _ in range(4)]
    color_compression, depth_compression = unpack(stream, "ii")
    color_width, color_height, depth_width, depth_height = unpack(stream, "IIII")
    depth_shift = unpack(stream, "f")[0]
    count = unpack(stream, "Q")[0]
    if not all((color_width, color_height, depth_width, depth_height, depth_shift)):
        raise PackageError("sens: invalid image dimensions or depth shift")
    return {
        "color_intrinsic": matrices[0][:3, :3],
        "depth_intrinsic": matrices[2][:3, :3],
        "color_compression": color_compression,
        "depth_compression": depth_compression,
        "color_size": (color_width, color_height),
        "depth_size": (depth_width, depth_height),
        "depth_shift": depth_shift,
        "frames": count,
    }


def is_rigid_transform(matrix: np.ndarray) -> bool:
    return (matrix.shape == (4, 4) and bool(np.isfinite(matrix).all())
            and np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-5)
            and np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-3)
            and bool(np.isclose(np.linalg.det(matrix[:3, :3]), 1, atol=1e-3)))


def alignment(scan_dir: Path, scan_id: str) -> list[list[float]]:
    metadata = scan_dir / f"{scan_id}.txt"
    if metadata.exists():
        for line in metadata.read_text(errors="replace").splitlines():
            key, separator, value = line.partition("=")
            if key.strip() == "axisAlignment" and separator:
                try:
                    values = [float(item) for item in value.split()]
                except ValueError as exc:
                    raise PackageError("alignment: invalid axisAlignment") from exc
                if len(values) != 16:
                    raise PackageError("alignment: invalid axisAlignment")
                matrix = np.array(values).reshape(4, 4)
                if not is_rigid_transform(matrix):
                    raise PackageError("alignment: axisAlignment must be a rigid transform")
                return matrix.tolist()
    raise PackageError(f"alignment: missing axisAlignment in {metadata.name}; supply valid alignment metadata before packing")


def verify(package: Path) -> dict:
    if package.suffix not in {".s3dpkg", ".partial"}:
        raise PackageError("name: expected .s3dpkg")
    with tarfile.open(package, "r:") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise PackageError("members: duplicate name")
        for member in members:
            path = Path(member.name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts
                    or "\\" in member.name or ":" in member.name):
                raise PackageError(f"members: unsafe name {member.name}")
        if "manifest.json" not in names:
            raise PackageError("manifest: missing")
        manifest = json.load(archive.extractfile("manifest.json"))
        if manifest.get("format_version") != "s3dpkg/2":
            raise PackageError("manifest: unsupported format_version; rerun preprocessing to create s3dpkg/2")
        if manifest.get("status") != "complete":
            raise PackageError("manifest: status must be complete")
        if not SCAN_RE.fullmatch(manifest.get("scan_id", "")):
            raise PackageError("manifest: invalid scan_id")
        source_alignment = np.asarray(manifest.get("source_axis_alignment"), dtype=np.float64)
        if (not is_rigid_transform(source_alignment)
                or manifest.get("coordinate_frame") != "axis_aligned"):
            raise PackageError("alignment: Package must contain axis_aligned coordinates and a valid source transform")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(names) != set(files) | {"manifest.json"}:
            raise PackageError("members: file list differs from manifest")
        required = {"mesh/vh_clean_2.ply", "mesh/superpoints.npy", "calib/intrinsics.json",
                    "frames/index.parquet"}
        if not required.issubset(files):
            raise PackageError("members: required file missing")
        frames = {name.split("/")[2].split(".")[0] for name in files
                  if name.startswith("frames/color/")}
        if not frames or any(f"frames/{part}/{fid}.{ext}" not in files
                             for fid in frames for part, ext in
                             (("depth", "png"), ("pose", "txt"))):
            raise PackageError("frames: incomplete keyframe")
        for member in members:
            if member.name == "manifest.json":
                continue
            digest = hashlib.sha256()
            source = archive.extractfile(member)
            while block := source.read(1024 * 1024):
                digest.update(block)
            if digest.hexdigest() != files[member.name]:
                raise PackageError(f"checksum: {member.name}")
        mesh = PlyData.read(io.BytesIO(archive.extractfile("mesh/vh_clean_2.ply").read()))
        points = np.load(io.BytesIO(archive.extractfile("mesh/superpoints.npy").read()),
                         allow_pickle=False)
        if points.dtype != np.int32 or points.ndim != 1 or len(points) != len(mesh["vertex"]):
            raise PackageError("superpoints: shape or dtype mismatch")
        return manifest


def pack(scan_dir: Path, output: Path, color_width: int = 960) -> Path:
    scan_id = scan_dir.name
    if not SCAN_RE.fullmatch(scan_id):
        raise PackageError("scan: directory name must be sceneXXXX_YY")
    sens = scan_dir / f"{scan_id}.sens"
    mesh = scan_dir / f"{scan_id}_vh_clean_2.ply"
    segs = scan_dir / f"{scan_id}_vh_clean_2.0.010000.segs.json"
    for file in (sens, mesh, segs):
        if not file.is_file():
            raise PackageError(f"scan: missing {file.name}")
    mesh_data = PlyData.read(mesh, mmap=False)
    vertices = len(mesh_data["vertex"])
    segments = np.asarray(json.loads(segs.read_text())["segIndices"], dtype=np.int32)
    if len(segments) != vertices:
        raise PackageError("superpoints: segIndices length differs from mesh vertices")
    axis_matrix = np.asarray(alignment(scan_dir, scan_id), dtype=np.float64)
    vertex = mesh_data["vertex"].data
    points = np.column_stack((vertex["x"], vertex["y"], vertex["z"], np.ones(vertices)))
    aligned_points = points @ axis_matrix.T
    for index, field in enumerate(("x", "y", "z")):
        vertex[field] = aligned_points[:, index]
    if {"nx", "ny", "nz"}.issubset(vertex.dtype.names):
        normals = np.column_stack((vertex["nx"], vertex["ny"], vertex["nz"])) @ axis_matrix[:3, :3].T
        for index, field in enumerate(("nx", "ny", "nz")):
            vertex[field] = normals[:, index]
    output.mkdir(parents=True, exist_ok=True)
    package = output / f"{scan_id}.s3dpkg"
    partial = output / f"{scan_id}.s3dpkg.partial"
    with tempfile.TemporaryDirectory(prefix="s3d-prep-") as tmp:
        root = Path(tmp)
        (root / "mesh").mkdir()
        (root / "calib").mkdir()
        for folder in ("color", "depth", "pose"):
            (root / "frames" / folder).mkdir(parents=True)
        mesh_data.write(root / "mesh/vh_clean_2.ply")
        np.save(root / "mesh/superpoints.npy", segments, allow_pickle=False)
        frame_rows = []
        with sens.open("rb") as stream:
            header = sens_header(stream)
            color_scale = min(1.0, color_width / max(header["color_size"]))
            color_size = tuple(max(1, round(dim * color_scale)) for dim in header["color_size"])
            color_intrinsic = header["color_intrinsic"].copy()
            color_intrinsic[0, :] *= color_size[0] / header["color_size"][0]
            color_intrinsic[1, :] *= color_size[1] / header["color_size"][1]
            calib = {
                "color": {"intrinsic": color_intrinsic.tolist(), "size": color_size},
                "depth": {"intrinsic": header["depth_intrinsic"].tolist(),
                          "size": header["depth_size"]},
                "depth_shift": header["depth_shift"],
            }
            (root / "calib/intrinsics.json").write_text(json.dumps(calib))
            for frame_id in range(header["frames"]):
                pose = np.array(unpack(stream, "16f"), dtype=np.float64).reshape(4, 4)
                unpack(stream, "QQ")  # timestamps
                color_bytes, depth_bytes = unpack(stream, "QQ")
                if color_bytes > 100_000_000 or depth_bytes > 100_000_000:
                    raise PackageError(f"sens: unreasonable frame size at {frame_id}")
                selected = frame_id % 10 == 0 and np.isfinite(pose).all()
                if not selected:
                    stream.seek(color_bytes + depth_bytes, 1)
                    continue
                color = read_exact(stream, color_bytes)
                depth = read_exact(stream, depth_bytes)
                if header["color_compression"] != 2 or header["depth_compression"] not in (0, 1):
                    raise PackageError("sens: unsupported image compression")
                image = Image.open(io.BytesIO(color)).convert("RGB")
                image = image.resize(color_size, Image.Resampling.LANCZOS)
                gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
                blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                raw_depth = zlib.decompress(depth) if header["depth_compression"] == 1 else depth
                expected = header["depth_size"][0] * header["depth_size"][1] * 2
                if len(raw_depth) != expected:
                    raise PackageError(f"sens: bad depth length at {frame_id}")
                depth_image = Image.fromarray(np.frombuffer(raw_depth, dtype="<u2")
                                              .reshape(header["depth_size"][1],
                                                       header["depth_size"][0]))
                fid = f"{frame_id:06d}"
                image.save(root / f"frames/color/{fid}.jpg", quality=90)
                depth_image.save(root / f"frames/depth/{fid}.png")
                np.savetxt(root / f"frames/pose/{fid}.txt", axis_matrix @ pose, fmt="%.9g")
                frame_rows.append({"frame_id": frame_id, "blur": blur, "valid": True})
        pq.write_table(pa.Table.from_pylist(frame_rows), root / "frames/index.parquet")
        files = {path.relative_to(root).as_posix(): sha256(path)
                 for path in root.rglob("*") if path.is_file()}
        manifest = {
            "format_version": "s3dpkg/2", "status": "complete", "scan_id": scan_id,
            "script_version": VERSION, "parameters": {"color_width": color_width, "stride": 10},
            "sens_sha256": sha256(sens), "coordinate_frame": "axis_aligned",
            "source_axis_alignment": axis_matrix.tolist(), "files": files,
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2))
        with tarfile.open(partial, "w:") as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
    try:
        verify(partial)
        partial.replace(package)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return package


def _batch_one(args: tuple[Path, str, Path, int]) -> dict:
    root, scan_id, output, color_width = args
    start = time.monotonic()
    destination = output / f"{scan_id}.s3dpkg"
    try:
        if not scan_id or scan_id in {".", ".."} or Path(scan_id).name != scan_id:
            raise PackageError("invalid scan ID")
        if destination.exists():
            verify(destination)
            status = "skipped"
        else:
            destination = pack(root / scan_id, output, color_width)
            status = "complete"
        error = ""
        size = destination.stat().st_size
    except (PackageError, OSError, ValueError, tarfile.TarError) as exc:
        status, size, error = "failed", 0, str(exc)
    return {"scene": scan_id, "status": status, "seconds": round(time.monotonic() - start, 2),
            "bytes": size, "error": error}


def batch(root: Path, list_file: Path, output: Path, color_width: int, workers: int = 1) -> None:
    if workers < 1:
        raise ValueError("--workers must be at least 1")
    output.mkdir(parents=True, exist_ok=True)
    scan_ids = [line.strip() for line in list_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")]
    if len(scan_ids) != len(set(scan_ids)):
        raise PackageError("duplicate scan ID in --list")
    tasks = [(root, scan_id, output, color_width) for scan_id in scan_ids]
    if workers == 1:
        rows = [_batch_one(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_batch_one, tasks))
    with (output / "prep_report.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scene", "status", "seconds", "bytes", "error"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("pack")
    p.add_argument("scan", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--color-width", type=int, default=960)
    v = commands.add_parser("verify")
    v.add_argument("package", type=Path)
    b = commands.add_parser("batch")
    b.add_argument("root", type=Path)
    b.add_argument("--list", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--color-width", type=int, default=960)
    b.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    try:
        if args.command == "pack":
            print(pack(args.scan, args.out, args.color_width))
        elif args.command == "verify":
            print(json.dumps(verify(args.package), indent=2))
        else:
            batch(args.root, args.list, args.out, args.color_width, args.workers)
    except (PackageError, OSError, ValueError, tarfile.TarError) as exc:
        parser.exit(1, f"{args.command}: {exc}\n")


if __name__ == "__main__":
    main()
