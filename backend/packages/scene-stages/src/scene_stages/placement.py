"""Where each Object is in the Scene, from the Objects' boxes in the gravity-aligned frame (floor at z = 0)."""

from typing import Literal

import numpy as np
from pydantic import BaseModel
from scene_core.domain import SceneObject
from scene_core.errors import SceneError
from scene_core.geometry import convex_hull

DEFAULTS = {
    "support_gap_m": 0.05,
    "support_overlap": 0.5,
    "wall_distance_m": 0.3,
    "num_neighbours": 2,
}
# Footprint edges whose directions differ by at least this much are different walls.
WALL_ANGLE = np.pi / 4


class Neighbour(BaseModel):
    id: str
    distance_m: float


class Placement(BaseModel):
    size_m: tuple[float, float, float]
    height_above_floor_m: float
    # "object": resting on support_id; "mounted": resting on neither an Object nor the floor.
    support: Literal["object", "floor", "mounted"]
    support_id: str | None = None
    neighbours: list[Neighbour]
    room_position: Literal["corner", "wall", "open"]


def placement_facts(objects: list[SceneObject], room_points, params=None) -> dict[str, Placement]:
    """Each Object's Placement by id. `room_points` are the mesh's vertices; their outline seen from
    above is the room's footprint, whose edges are its walls."""
    params = {**DEFAULTS, **(params or {})}
    for name in DEFAULTS:
        if not float(params[name]) > 0:
            raise SceneError("INVALID_PARAMETERS", f"{name} must be positive, got {params[name]}")
    footprints = [_footprint(obj) for obj in objects]
    bottoms = [obj.box.center[2] - obj.box.size[2] / 2 for obj in objects]
    tops = [obj.box.center[2] + obj.box.size[2] / 2 for obj in objects]
    bounds = [_bounds(f, b, t) for f, b, t in zip(footprints, bottoms, tops, strict=True)]
    hull = convex_hull(np.asarray(room_points, dtype=float).reshape(-1, 3)[:, :2])
    walls = [(a, b) for a, b in zip(hull, np.roll(hull, -1, axis=0), strict=True)]
    facts = {}
    for i, obj in enumerate(objects):
        support, support_id, best = "mounted", None, 0.0
        area = _area(footprints[i])
        for j, other in enumerate(objects):
            if j == i or abs(bottoms[i] - tops[j]) > params["support_gap_m"]:
                continue
            overlap = _area(_clip(footprints[i], footprints[j])) / area if area else 0.0
            if overlap >= params["support_overlap"] and overlap > best:
                support, support_id, best = "object", other.id, overlap
        if support_id is None and abs(bottoms[i]) <= params["support_gap_m"]:
            support = "floor"
        gaps = sorted((_gap(bounds[i], bounds[j]), j) for j in range(len(objects)) if j != i)[
            : int(params["num_neighbours"])
        ]
        facts[obj.id] = Placement(
            size_m=tuple(float(v) for v in obj.box.size),
            height_above_floor_m=float(bottoms[i]),
            support=support,
            support_id=support_id,
            neighbours=[Neighbour(id=objects[j].id, distance_m=float(d)) for d, j in gaps],
            room_position=_room_position(footprints[i], walls, params["wall_distance_m"]),
        )
    return facts


def _footprint(obj):
    """The box's four corners seen from above, counter-clockwise."""
    (x, y, _), (w, d, _) = obj.box.center, obj.box.size
    c, s = np.cos(obj.box.yaw), np.sin(obj.box.yaw)
    local = np.array([[-w, -d], [w, -d], [w, d], [-w, d]]) / 2
    return local @ np.array([[c, s], [-s, c]]) + (x, y)


def _bounds(footprint, bottom, top):
    return np.array([*footprint.min(axis=0), bottom]), np.array([*footprint.max(axis=0), top])


def _gap(a, b):
    """The distance between two axis-aligned bounds, 0 where they overlap."""
    return float(np.linalg.norm(np.maximum(0, np.maximum(a[0] - b[1], b[0] - a[1]))))


def _area(polygon):
    if len(polygon) < 3:
        return 0.0
    x, y = polygon[:, 0], polygon[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2)


def _clip(subject, clip):
    """The intersection of two convex counter-clockwise polygons (Sutherland-Hodgman)."""
    output = list(subject)
    for a, b in zip(clip, np.roll(clip, -1, axis=0), strict=True):
        edge = b - a

        def inside(p, a=a, edge=edge):
            return edge[0] * (p[1] - a[1]) - edge[1] * (p[0] - a[0]) >= 0

        points, output = output, []
        for k, current in enumerate(points):
            previous = points[k - 1]
            if inside(current) != inside(previous):
                direction = current - previous
                denominator = edge[0] * direction[1] - edge[1] * direction[0]
                t = (edge[1] * (previous[0] - a[0]) - edge[0] * (previous[1] - a[1])) / denominator
                output.append(previous + t * direction)
            if inside(current):
                output.append(current)
        if not output:
            break
    return np.asarray(output).reshape(-1, 2)


def _room_position(footprint, walls, distance):
    """corner when the box is near two walls of different directions, wall near one, else open."""
    directions = []
    for a, b in walls:
        edge = b - a
        length = np.dot(edge, edge)
        if not length:
            continue
        t = np.clip((footprint - a) @ edge / length, 0, 1)
        if np.linalg.norm(footprint - (a + t[:, None] * edge), axis=1).min() <= distance:
            directions.append(np.arctan2(edge[1], edge[0]) % np.pi)
    for k, first in enumerate(directions):
        for second in directions[k + 1 :]:
            difference = abs(first - second)
            if min(difference, np.pi - difference) >= WALL_ANGLE:
                return "corner"
    return "wall" if directions else "open"
