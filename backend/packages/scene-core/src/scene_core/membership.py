"""Object membership: which points of mesh/points.ply and which vertices of mesh/mesh.glb belong to
each Object. The binary layout below is the contract with the viewer (docs/architecture/api.md).

All integers are little-endian uint32 and every section starts at a multiple of 4 bytes, so a browser
views each array in place with `new Uint32Array(buffer, offset, length)`:

    magic "SCMB" | version 1 | object_count N | point_count | vertex_count | ids_byte_length L
    ids: UTF-8 JSON array of the N Object ids, space-padded to L (a multiple of 4)
    point_offsets[N + 1] | point_indices[point_offsets[N]]
    vertex_offsets[N + 1] | vertex_indices[vertex_offsets[N]]

Object i owns point_indices[point_offsets[i]:point_offsets[i + 1]], sorted ascending and unique; the
vertex arrays work the same way. A point may belong to several Objects or to none.
"""

import json
import struct
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

MAGIC = b"SCMB"
VERSION = 1
_HEADER = struct.Struct("<4s5I")


@dataclass(frozen=True)
class ObjectMembership:
    ids: list[str]
    point_count: int
    vertex_count: int
    point_offsets: np.ndarray
    point_indices: np.ndarray
    vertex_offsets: np.ndarray
    vertex_indices: np.ndarray

    @classmethod
    def from_lists(
        cls,
        ids: Sequence[str],
        points: Sequence[np.ndarray],
        vertices: Sequence[np.ndarray],
        point_count: int,
        vertex_count: int,
    ) -> "ObjectMembership":
        """One index array per Object, in Object order; each is sorted and deduplicated here."""
        if not len(ids) == len(points) == len(vertices):
            raise ValueError("Every Object needs one point list and one vertex list")
        point_offsets, point_indices = _csr(points, point_count)
        vertex_offsets, vertex_indices = _csr(vertices, vertex_count)
        return cls(
            list(ids),
            point_count,
            vertex_count,
            point_offsets,
            point_indices,
            vertex_offsets,
            vertex_indices,
        )

    def points(self, index: int) -> np.ndarray:
        return self.point_indices[self.point_offsets[index] : self.point_offsets[index + 1]]

    def vertices(self, index: int) -> np.ndarray:
        return self.vertex_indices[self.vertex_offsets[index] : self.vertex_offsets[index + 1]]

    def encode(self) -> bytes:
        ids = json.dumps(self.ids, ensure_ascii=False, separators=(",", ":")).encode()
        ids += b" " * (-len(ids) % 4)
        header = _HEADER.pack(
            MAGIC, VERSION, len(self.ids), self.point_count, self.vertex_count, len(ids)
        )
        arrays = (self.point_offsets, self.point_indices, self.vertex_offsets, self.vertex_indices)
        return header + ids + b"".join(a.astype("<u4").tobytes() for a in arrays)

    @classmethod
    def decode(cls, data: bytes) -> "ObjectMembership":
        """Parse and check an encoded file; any malformed content raises ValueError."""
        if len(data) < _HEADER.size:
            raise ValueError("Membership file is truncated")
        magic, version, count, point_count, vertex_count, ids_length = _HEADER.unpack_from(data)
        if magic != MAGIC or version != VERSION:
            raise ValueError("Not a version 1 membership file")
        if ids_length % 4 or _HEADER.size + ids_length > len(data):
            raise ValueError("Membership ids section is malformed")
        ids = json.loads(data[_HEADER.size : _HEADER.size + ids_length].decode())
        if (
            not isinstance(ids, list)
            or len(ids) != count
            or not all(isinstance(i, str) for i in ids)
        ):
            raise ValueError("Membership ids do not match the Object count")
        position = _HEADER.size + ids_length
        sections = []
        for total in (point_count, vertex_count):
            offsets = _read(data, position, count + 1)
            position += offsets.nbytes
            if offsets[0] != 0 or np.any(np.diff(offsets.astype(np.int64)) < 0):
                raise ValueError("Membership offsets must start at 0 and never decrease")
            indices = _read(data, position, int(offsets[-1]))
            position += indices.nbytes
            if len(indices) and indices.max() >= total:
                raise ValueError("Membership index out of range")
            sections += [offsets, indices]
        if position != len(data):
            raise ValueError("Membership file has trailing bytes")
        return cls(ids, point_count, vertex_count, *sections)


def _csr(lists, total):
    unique = [np.unique(np.asarray(values, dtype=np.int64)) for values in lists]
    if any(len(u) and (u[0] < 0 or u[-1] >= total) for u in unique):
        raise ValueError("Membership index out of range")
    offsets = np.zeros(len(unique) + 1, dtype=np.uint32)
    offsets[1:] = np.cumsum([len(u) for u in unique])
    indices = np.concatenate(unique).astype(np.uint32) if unique else np.zeros(0, np.uint32)
    return offsets, indices


def _read(data, position, length):
    if position + 4 * length > len(data):
        raise ValueError("Membership file is truncated")
    return np.frombuffer(data, dtype="<u4", count=length, offset=position)
