"""Box and plane fitting for gravity-aligned geometry; NumPy only."""

import numpy as np

from .domain import OrientedBox


def _cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def convex_hull(points):
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
    hull = convex_hull(points[:, :2])
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
