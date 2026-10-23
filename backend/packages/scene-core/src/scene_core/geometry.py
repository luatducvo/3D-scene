"""Metric geometry for gravity-aligned oriented boxes; NumPy only."""

import numpy as np

from .domain import OrientedBox


def _box(value):
    return value.box if hasattr(value, "box") else value


def footprint(box):
    box = _box(box)
    half = np.asarray(box.size[:2]) / 2
    corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * half
    c, s = np.cos(box.yaw), np.sin(box.yaw)
    return corners @ np.array([[c, s], [-s, c]]) + box.center[:2]


def _cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def _clip(subject, clip):
    output = list(subject)
    for a, b in zip(clip, np.roll(clip, -1, axis=0), strict=True):
        source, output = output, []
        if not source:
            break
        previous = source[-1]
        for current in source:
            inside = _cross(b - a, current - a) >= -1e-10
            previous_inside = _cross(b - a, previous - a) >= -1e-10
            if inside != previous_inside:
                direction = current - previous
                denominator = _cross(direction, b - a)
                if abs(denominator) > 1e-12:
                    output.append(previous + _cross(a - previous, b - a) / denominator * direction)
            if inside:
                output.append(current)
            previous = current
    return np.asarray(output)


def footprint_overlap(a, b):
    polygon = _clip(footprint(a), footprint(b))
    if len(polygon) < 3:
        return 0.0
    return (
        abs(
            float(
                np.sum(
                    polygon[:, 0] * np.roll(polygon[:, 1], -1)
                    - polygon[:, 1] * np.roll(polygon[:, 0], -1)
                )
            )
        )
        / 2
    )


def _point_segment_distance(point, a, b):
    edge = b - a
    length = np.dot(edge, edge)
    t = np.clip(np.dot(point - a, edge) / length, 0, 1) if length else 0
    return float(np.linalg.norm(point - (a + t * edge)))


def box_surface_distance(a, b):
    a, b = _box(a), _box(b)
    pa, pb = footprint(a), footprint(b)
    # Convex clipping handles touching footprints, including edge intersections.
    overlap = _clip(pa, pb)
    xy = (
        0.0
        if len(overlap)
        else min(
            _point_segment_distance(point, edge_a, edge_b)
            for points, polygon in ((pa, pb), (pb, pa))
            for point in points
            for edge_a, edge_b in zip(polygon, np.roll(polygon, -1, axis=0), strict=True)
        )
    )
    z = max(0, abs(a.center[2] - b.center[2]) - (a.size[2] + b.size[2]) / 2)
    return float(np.hypot(xy, z))


def _convex_hull(points):
    points = sorted(set(map(tuple, points)))
    if len(points) <= 2:
        return np.asarray(points)
    halves = []
    for sequence in (points, reversed(points)):
        half = []
        for point in sequence:
            while (
                len(half) >= 2
                and _cross(np.subtract(half[-1], half[-2]), np.subtract(point, half[-1])) <= 0
            ):
                half.pop()
            half.append(point)
        halves.append(half[:-1])
    return np.asarray(halves[0] + halves[1])


def fit_box(points):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points) or not np.isfinite(points).all():
        raise ValueError("Box points must be a nonempty finite N x 3 array")
    hull = _convex_hull(points[:, :2])
    edges = np.roll(hull, -1, axis=0) - hull
    angles = np.unique(np.mod(np.arctan2(edges[:, 1], edges[:, 0]), np.pi / 2))
    best = None
    for yaw in angles:
        c, s = np.cos(yaw), np.sin(yaw)
        rotation = np.array([[c, -s], [s, c]])
        local = points[:, :2] @ rotation
        low, high = local.min(axis=0), local.max(axis=0)
        area = np.prod(high - low)
        if best is None or area < best[0]:
            best = area, yaw, rotation, low, high
    _, yaw, rotation, low, high = best
    center_xy = (low + high) / 2 @ rotation.T
    zmin, zmax = points[:, 2].min(), points[:, 2].max()
    return OrientedBox(
        center=(*center_xy, (zmin + zmax) / 2), size=(*(high - low), zmax - zmin), yaw=float(yaw)
    )


def fit_plane(points, threshold=0.02, iterations=300, seed=42):
    points = np.asarray(points, dtype=float)
    if len(points) < 3:
        raise ValueError("At least three points required")
    rng, best = np.random.default_rng(seed), None
    for _ in range(iterations):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        length = np.linalg.norm(normal)
        if length < 1e-10:
            continue
        normal /= length
        mask = abs(points @ normal - a @ normal) <= threshold
        if best is None or mask.sum() > best.sum():
            best = mask
    if best is None or best.sum() < 3:
        raise ValueError("No non-degenerate plane found")
    center = points[best].mean(axis=0)
    _, _, vectors = np.linalg.svd(points[best] - center, full_matrices=False)
    normal = vectors[-1]
    if normal[2] < 0:
        normal = -normal
    offset = -float(center @ normal)
    return normal, offset, abs(points @ normal + offset) <= threshold
